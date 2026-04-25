from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, NamedTuple, Sequence

from ._constants import (
    CHARACTER_AVAILABILITY_KEY,
    PARTNER_DISTRIBUTIONS_KEY,
    PROMPT_LIST_KEYS,
    SETTING_AVAILABILITY_KEY,
    TITLE_TOKEN_PATTERN,
)
from ._range_utils import add_clipped_range_checkpoints


class DatasetLintReport(NamedTuple):
    errors: list[str]
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


class _IntervalLintResults(NamedTuple):
    missing_character_ranges: list[tuple[date, date]]
    thin_character_ranges: list[tuple[date, date]]
    missing_setting_ranges: list[tuple[date, date]]
    thin_setting_ranges: list[tuple[date, date]]
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]]


class _AvailabilityGapFlags(NamedTuple):
    missing_characters: bool
    thin_characters: bool
    missing_settings: bool
    thin_settings: bool


def _format_date_ranges(ranges: list[tuple[date, date]]) -> str:
    if not ranges:
        return "none"
    rendered = []
    for start, end in ranges:
        if start == end:
            rendered.append(start.isoformat())
        else:
            rendered.append(f"{start.isoformat()}..{end.isoformat()}")
    return ", ".join(rendered)


def _coalesce_ranges(ranges: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda item: item[0])
    merged: list[tuple[date, date]] = [sorted_ranges[0]]
    one_day = timedelta(days=1)
    for current_start, current_end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end + one_day:
            merged[-1] = (last_start, max(last_end, current_end))
            continue
        merged.append((current_start, current_end))
    return merged


def build_coverage_checkpoints(
    data: Mapping[str, Any], *, range_start: date, range_end: date
) -> list[date]:
    one_day = timedelta(days=1)
    checkpoints: set[date] = {range_start}
    checkpoints.add(range_end + one_day if range_end < date.max else range_end)

    for source in (data[CHARACTER_AVAILABILITY_KEY], data[SETTING_AVAILABILITY_KEY]):
        add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=((row_start, row_end) for _, row_start, row_end in source),
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


def _available_entities(
    availability_rows: Sequence[tuple[str, date, date]], *, selected_date: date
) -> list[str]:
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
    return _AvailabilityGapFlags(
        missing_characters=len(characters) < 2,
        thin_characters=len(characters) == 2,
        missing_settings=len(settings) == 0,
        thin_settings=len(settings) == 1,
    )


def _record_partner_gaps(
    *,
    partner_distributions: Mapping[str, Sequence[Mapping[str, date]]],
    interval: tuple[date, date],
    protagonists: Sequence[str],
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]],
) -> None:
    current_start, _ = interval
    for protagonist in protagonists:
        eras = partner_distributions.get(protagonist, [])
        has_partner_data = any(era["date_start"] <= current_start <= era["date_end"] for era in eras)
        if not has_partner_data:
            partner_data_gap_ranges_by_protagonist.setdefault(
                protagonist, []
            ).append(interval)


def _collect_interval_lint_ranges(
    data: Mapping[str, Any], *, sorted_checkpoints: Sequence[date], range_end: date
) -> _IntervalLintResults:
    one_day = timedelta(days=1)
    missing_character_ranges: list[tuple[date, date]] = []
    thin_character_ranges: list[tuple[date, date]] = []
    missing_setting_ranges: list[tuple[date, date]] = []
    thin_setting_ranges: list[tuple[date, date]] = []
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]] = {}

    for index, current_start in enumerate(sorted_checkpoints):
        interval_end = _resolve_interval_end(
            index=index,
            current_start=current_start,
            sorted_checkpoints=sorted_checkpoints,
            range_end=range_end,
            one_day=one_day,
        )
        if interval_end is None:
            continue
        interval = (current_start, interval_end)
        characters = _available_entities(
            data[CHARACTER_AVAILABILITY_KEY], selected_date=current_start
        )
        settings = _available_entities(
            data[SETTING_AVAILABILITY_KEY], selected_date=current_start
        )
        gap_flags = _availability_gap_flags(
            characters=characters,
            settings=settings,
        )
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


def _append_coverage_messages(
    *,
    errors: list[str],
    warnings: list[str],
    interval_results: _IntervalLintResults,
) -> None:
    if interval_results.missing_character_ranges:
        errors.append(
            "Coverage gap: fewer than two distinct characters on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.missing_character_ranges))}."
        )
    if interval_results.missing_setting_ranges:
        errors.append(
            "Coverage gap: no available settings on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.missing_setting_ranges))}."
        )
    if interval_results.thin_character_ranges:
        warnings.append(
            "Fragile coverage: exactly two characters available on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.thin_character_ranges))}."
        )
    if interval_results.thin_setting_ranges:
        warnings.append(
            "Fragile coverage: exactly one setting available on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.thin_setting_ranges))}."
        )
    for protagonist in sorted(interval_results.partner_data_gap_ranges_by_protagonist):
        gap_ranges = _coalesce_ranges(
            interval_results.partner_data_gap_ranges_by_protagonist[protagonist]
        )
        warnings.append(
            "Partner data coverage gap: protagonist "
            f"'{protagonist}' has no partner era data available on "
            f"{_format_date_ranges(gap_ranges)}."
        )


def _append_prompt_depth_warnings(data: Mapping[str, Any], *, warnings: list[str]) -> None:
    for key in PROMPT_LIST_KEYS:
        options = data[key]
        if len(options) >= 3:
            continue
        warnings.append(
            f"Prompt depth warning: {key} has only {len(options)} option(s); "
            "consider adding at least 3 for variety."
        )

    if len(data["word_count_targets"]) < 3:
        warnings.append(
            "Prompt depth warning: word_count_targets has fewer than 3 options; "
            "consider adding more range variety."
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

    tokens_seen: set[str] = set()
    for template in data["titles"]:
        tokens_seen.update(TITLE_TOKEN_PATTERN.findall(template))
    missing_title_tokens = sorted({"protagonist", "setting", "time_period"} - tokens_seen)
    if missing_title_tokens:
        warnings.append(
            "Title coverage gap: token(s) never used in templates: "
            f"{', '.join(f'@{token}' for token in missing_title_tokens)}."
        )

    _append_prompt_depth_warnings(data, warnings=warnings)

    return DatasetLintReport(errors=errors, warnings=warnings)


def emit_lint_report(report: DatasetLintReport) -> None:
    if report.errors:
        print("Dataset lint: errors")
        for message in report.errors:
            print(f"  - {message}")
    else:
        print("Dataset lint: no blocking coverage gaps found.")

    if report.warnings:
        print("Dataset lint: warnings")
        for message in report.warnings:
            print(f"  - {message}")
    else:
        print("Dataset lint: no warnings.")
