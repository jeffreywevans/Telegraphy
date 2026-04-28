from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Mapping, NamedTuple, Sequence, TextIO

from ._constants import (
    CHARACTER_AVAILABILITY_KEY,
    PARTNER_DISTRIBUTIONS_KEY,
    PROMPT_LIST_KEYS,
    SETTING_AVAILABILITY_KEY,
    TITLE_TOKEN_PATTERN,
)
from ._range_utils import add_clipped_range_checkpoints

DateRange = tuple[date, date]
AvailabilityRows = Sequence[tuple[str, date, date]]
PartnerEras = Sequence[Mapping[str, Any]]
PartnerDistributions = Mapping[str, PartnerEras]
PartnerGapRanges = dict[str, list[DateRange]]

_REQUIRED_TITLE_TOKENS = frozenset({"protagonist", "setting", "time_period"})
_MINIMUM_PROMPT_OPTIONS = 3
_MINIMUM_CHARACTER_CHOICES = 2
_MINIMUM_SETTING_CHOICES = 1
_ONE_DAY = timedelta(days=1)


class DatasetLintReport(NamedTuple):
    errors: list[str]
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


class _IntervalLintResults(NamedTuple):
    missing_character_ranges: list[DateRange]
    thin_character_ranges: list[DateRange]
    missing_setting_ranges: list[DateRange]
    thin_setting_ranges: list[DateRange]
    partner_data_gap_ranges_by_protagonist: PartnerGapRanges


class _AvailabilityGapFlags(NamedTuple):
    missing_characters: bool
    thin_characters: bool
    missing_settings: bool
    thin_settings: bool


def _format_date_range(date_range: DateRange) -> str:
    """Render one closed date range in the lint-report house style."""
    start, end = date_range
    start_text = start.isoformat()
    end_text = end.isoformat()
    return start_text if start == end else f"{start_text}..{end_text}"


def _format_date_ranges(ranges: list[DateRange]) -> str:
    """Render closed date ranges compactly for human-facing diagnostics."""
    if not ranges:
        return "none"
    return ", ".join(_format_date_range(date_range) for date_range in ranges)


def _merge_or_append_range(merged: list[DateRange], current: DateRange) -> None:
    """Merge an adjacent/overlapping range into ``merged`` or append it.

    """
    current_start, current_end = current
    last_start, last_end = merged[-1]
    if current_start <= last_end + _ONE_DAY:
        merged[-1] = (last_start, max(last_end, current_end))
    else:
        merged.append(current)


def _coalesce_ranges(ranges: list[DateRange]) -> list[DateRange]:
    """Return sorted closed ranges with overlaps and adjacent spans coalesced."""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda item: item[0])
    merged = [sorted_ranges[0]]
    for current in sorted_ranges[1:]:
        _merge_or_append_range(merged, current)
    return merged


def build_coverage_checkpoints(
    data: Mapping[str, Any], *, range_start: date, range_end: date
) -> list[date]:
    """Build interval boundaries where availability or partner data can change."""
    checkpoints = {range_start}
    checkpoints.add(_next_day_or_final_day(range_end))

    for rows in (data[CHARACTER_AVAILABILITY_KEY], data[SETTING_AVAILABILITY_KEY]):
        add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=((row_start, row_end) for _, row_start, row_end in rows),
            range_start=range_start,
            range_end=range_end,
        )

    for eras in data[PARTNER_DISTRIBUTIONS_KEY].values():
        add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=((era["date_start"], era["date_end"]) for era in eras),
            range_start=range_start,
            range_end=range_end,
        )

    return sorted(checkpoints)


def _next_day_or_final_day(day: date) -> date:
    """Return the next day, clamping at ``date.max`` to avoid overflow."""
    if day == date.max:
        return day
    return day + _ONE_DAY


def _available_entities(availability_rows: AvailabilityRows, *, selected_date: date) -> list[str]:
    """Return names whose closed availability window contains ``selected_date``."""
    return [
        name
        for name, start_date, end_date in availability_rows
        if start_date <= selected_date <= end_date
    ]


def _resolve_interval_end(
    *,
    index: int,
    current_start: date,
    sorted_checkpoints: Sequence[date],
    range_end: date,
    one_day: timedelta,
) -> date | None:
    """Resolve a closed interval end from a checkpoint list."""
    if index + 1 < len(sorted_checkpoints):
        interval_end = min(range_end, sorted_checkpoints[index + 1] - one_day)
    else:
        interval_end = range_end
    return None if interval_end < current_start else interval_end


def _availability_gap_flags(
    *,
    characters: Sequence[str],
    settings: Sequence[str],
) -> _AvailabilityGapFlags:
    """Classify blocking and fragile availability counts for one interval."""
    character_count = len(characters)
    setting_count = len(settings)
    return _AvailabilityGapFlags(
        missing_characters=character_count < _MINIMUM_CHARACTER_CHOICES,
        thin_characters=character_count == _MINIMUM_CHARACTER_CHOICES,
        missing_settings=setting_count < _MINIMUM_SETTING_CHOICES,
        thin_settings=setting_count == _MINIMUM_SETTING_CHOICES,
    )


def _era_covers_date(era: Mapping[str, Any], *, selected_date: date) -> bool:
    return era["date_start"] <= selected_date <= era["date_end"]


def _has_partner_data(eras: PartnerEras, *, selected_date: date) -> bool:
    return any(_era_covers_date(era, selected_date=selected_date) for era in eras)


def _record_partner_gaps(
    *,
    partner_distributions: PartnerDistributions,
    interval: DateRange,
    protagonists: Sequence[str],
    partner_data_gap_ranges_by_protagonist: PartnerGapRanges,
) -> None:
    """Record intervals where available protagonists have no partner era data."""
    current_start, _ = interval
    for protagonist in protagonists:
        eras = partner_distributions.get(protagonist, ())
        if _has_partner_data(eras, selected_date=current_start):
            continue
        partner_data_gap_ranges_by_protagonist.setdefault(protagonist, []).append(interval)


def _collect_interval_lint_ranges(
    data: Mapping[str, Any], *, sorted_checkpoints: Sequence[date], range_end: date
) -> _IntervalLintResults:
    missing_character_ranges: list[DateRange] = []
    thin_character_ranges: list[DateRange] = []
    missing_setting_ranges: list[DateRange] = []
    thin_setting_ranges: list[DateRange] = []
    partner_data_gap_ranges_by_protagonist: PartnerGapRanges = {}

    for index, current_start in enumerate(sorted_checkpoints):
        interval_end = _resolve_interval_end(
            index=index,
            current_start=current_start,
            sorted_checkpoints=sorted_checkpoints,
            range_end=range_end,
            one_day=_ONE_DAY,
        )
        if interval_end is None:
            continue

        interval = (current_start, interval_end)
        characters = _available_entities(
            data[CHARACTER_AVAILABILITY_KEY], selected_date=current_start
        )
        settings = _available_entities(data[SETTING_AVAILABILITY_KEY], selected_date=current_start)
        gap_flags = _availability_gap_flags(characters=characters, settings=settings)

        if gap_flags.missing_characters:
            missing_character_ranges.append(interval)
        elif gap_flags.thin_characters:
            thin_character_ranges.append(interval)

        if gap_flags.missing_settings:
            missing_setting_ranges.append(interval)
        elif gap_flags.thin_settings:
            thin_setting_ranges.append(interval)

        _record_partner_gaps(
            partner_distributions=data[PARTNER_DISTRIBUTIONS_KEY],
            interval=interval,
            protagonists=characters,
            partner_data_gap_ranges_by_protagonist=partner_data_gap_ranges_by_protagonist,
        )

    return _IntervalLintResults(
        missing_character_ranges=missing_character_ranges,
        thin_character_ranges=thin_character_ranges,
        missing_setting_ranges=missing_setting_ranges,
        thin_setting_ranges=thin_setting_ranges,
        partner_data_gap_ranges_by_protagonist=partner_data_gap_ranges_by_protagonist,
    )


def _coalesced_date_ranges(ranges: list[DateRange]) -> str:
    return _format_date_ranges(_coalesce_ranges(ranges))


def _append_coverage_messages(
    *,
    errors: list[str],
    warnings: list[str],
    interval_results: _IntervalLintResults,
) -> None:
    """Append blocking errors and non-blocking warnings from interval analysis."""
    if interval_results.missing_character_ranges:
        errors.append(
            "Coverage gap: fewer than two distinct characters on "
            f"{_coalesced_date_ranges(interval_results.missing_character_ranges)}."
        )
    if interval_results.missing_setting_ranges:
        errors.append(
            "Coverage gap: no available settings on "
            f"{_coalesced_date_ranges(interval_results.missing_setting_ranges)}."
        )
    if interval_results.thin_character_ranges:
        warnings.append(
            "Fragile coverage: exactly two characters available on "
            f"{_coalesced_date_ranges(interval_results.thin_character_ranges)}."
        )
    if interval_results.thin_setting_ranges:
        warnings.append(
            "Fragile coverage: exactly one setting available on "
            f"{_coalesced_date_ranges(interval_results.thin_setting_ranges)}."
        )

    for protagonist in sorted(interval_results.partner_data_gap_ranges_by_protagonist):
        gap_ranges = interval_results.partner_data_gap_ranges_by_protagonist[protagonist]
        warnings.append(
            "Partner data coverage gap: protagonist "
            f"'{protagonist}' has no partner era data available on "
            f"{_coalesced_date_ranges(gap_ranges)}."
        )


def _append_prompt_depth_warnings(data: Mapping[str, Any], *, warnings: list[str]) -> None:
    """Warn when prompt lists are too shallow for durable random variety."""
    for key in PROMPT_LIST_KEYS:
        option_count = len(data[key])
        if option_count >= _MINIMUM_PROMPT_OPTIONS:
            continue
        warnings.append(
            f"Prompt depth warning: {key} has only {option_count} option(s); "
            f"consider adding at least {_MINIMUM_PROMPT_OPTIONS} for variety."
        )

    if len(data["word_count_targets"]) < _MINIMUM_PROMPT_OPTIONS:
        warnings.append(
            "Prompt depth warning: word_count_targets has fewer than "
            f"{_MINIMUM_PROMPT_OPTIONS} options; "
            "consider adding more range variety."
        )


def _append_title_token_warnings(data: Mapping[str, Any], *, warnings: list[str]) -> None:
    tokens_seen: set[str] = set()
    for template in data["titles"]:
        tokens_seen.update(TITLE_TOKEN_PATTERN.findall(template))

    missing_title_tokens = sorted(_REQUIRED_TITLE_TOKENS - tokens_seen)
    if missing_title_tokens:
        warnings.append(
            "Title coverage gap: token(s) never used in templates: "
            f"{', '.join(f'@{token}' for token in missing_title_tokens)}."
        )


def lint_story_data(data: Mapping[str, Any]) -> DatasetLintReport:
    """Report actionable dataset diagnostics and coverage gaps."""
    range_start = data["date_start"]
    range_end = data["date_end"]
    sorted_checkpoints = build_coverage_checkpoints(
        data, range_start=range_start, range_end=range_end
    )
    interval_results = _collect_interval_lint_ranges(
        data, sorted_checkpoints=sorted_checkpoints, range_end=range_end
    )

    errors: list[str] = []
    warnings: list[str] = []
    _append_coverage_messages(
        errors=errors,
        warnings=warnings,
        interval_results=interval_results,
    )
    _append_title_token_warnings(data, warnings=warnings)
    _append_prompt_depth_warnings(data, warnings=warnings)

    return DatasetLintReport(errors=errors, warnings=warnings)


def _emit_lint_section(
    *,
    heading: str,
    empty_message: str,
    messages: Sequence[str],
    file: TextIO,
) -> None:
    if not messages:
        print(empty_message, file=file)
        return

    print(heading, file=file)
    for message in messages:
        print(f"  - {message}", file=file)


def emit_lint_report(report: DatasetLintReport, *, file: TextIO | None = None) -> None:
    """Print a deterministic, human-readable lint report."""
    destination = sys.stdout if file is None else file
    _emit_lint_section(
        heading="Dataset lint: errors",
        empty_message="Dataset lint: no blocking coverage gaps found.",
        messages=report.errors,
        file=destination,
    )
    _emit_lint_section(
        heading="Dataset lint: warnings",
        empty_message="Dataset lint: no warnings.",
        messages=report.warnings,
        file=destination,
    )
