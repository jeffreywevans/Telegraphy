from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, TypeAlias, TypedDict, cast


class PartnerWeightInput(TypedDict):
    partner: str
    weight: float | int


class PartnerEraInput(TypedDict):
    date_start: str
    date_end: str
    partners: list[PartnerWeightInput]


class CharacterPartnerDistributionInput(TypedDict):
    character: str
    date_start: str
    date_end: str
    eras: list[PartnerEraInput]


class PartnerDistributionPayloadInput(TypedDict):
    schema_version: int
    dataset_version: str
    date_start: str
    date_end: str
    partner_distributions: list[CharacterPartnerDistributionInput]


LegacyPartnerWeight: TypeAlias = tuple[str, float]


class LegacyPartnerEra(TypedDict):
    date_start: date
    date_end: date
    partners: list[LegacyPartnerWeight]


LegacyPartnerIndex: TypeAlias = dict[str, list[LegacyPartnerEra]]


def _reject_when(condition: bool, message: str) -> None:
    if condition:
        raise ValueError(message)


def require_keys(
    section_name: str, payload: dict[str, object], required: AbstractSet[str]
) -> None:
    missing = sorted(required - payload.keys())
    _reject_when(
        bool(missing),
        f"{section_name}: missing required keys: {', '.join(missing)}",
    )


@dataclass(frozen=True, slots=True)
class PartnerWeight:
    partner: str
    weight: float


@dataclass(frozen=True, slots=True)
class PartnerEra:
    date_start: date
    date_end: date
    partners: tuple[PartnerWeight, ...]

    def covers(self, candidate: date) -> bool:
        return self.date_start <= candidate <= self.date_end

    def to_legacy_dict(self) -> LegacyPartnerEra:
        return {
            "date_start": self.date_start,
            "date_end": self.date_end,
            "partners": [(entry.partner, entry.weight) for entry in self.partners],
        }


@dataclass(frozen=True, slots=True)
class CharacterPartnerDistribution:
    character: str
    date_start: date
    date_end: date
    eras: tuple[PartnerEra, ...]


@dataclass(frozen=True, slots=True)
class PartnerDistributionDataset:
    schema_version: int
    dataset_version: str
    date_start: date
    date_end: date
    by_character: dict[str, CharacterPartnerDistribution]

    def to_legacy_index(self) -> LegacyPartnerIndex:
        return {
            character: [era.to_legacy_dict() for era in distribution.eras]
            for character, distribution in self.by_character.items()
        }


def _parse_iso_date(raw: object, *, field: str) -> date:
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)") from exc


def _parse_name(value: object, *, field: str) -> str:
    parsed = str(value).strip()
    _reject_when(not parsed, f"{field} must be a non-empty string")
    return parsed


def _is_real_number(raw: object) -> bool:
    return not isinstance(raw, bool) and isinstance(raw, (int, float))


def _parse_weight(raw: object, *, field: str) -> float:
    _reject_when(not _is_real_number(raw), f"{field} must be a real number")

    weight = float(cast(float | int, raw))
    _reject_when(
        not math.isfinite(weight) or weight < 0,
        f"{field} must be finite and non-negative",
    )
    return weight


def _require_non_empty_list(value: object, *, field: str) -> list[object]:
    _reject_when(
        not isinstance(value, list) or not value,
        f"{field} must be a non-empty list",
    )
    return cast(list[object], value)


def _require_dict(value: object, *, field: str) -> dict[str, object]:
    _reject_when(not isinstance(value, dict), f"{field} must be an object")
    return cast(dict[str, object], value)


def _parse_partners(era_section: str, partners_raw: object) -> tuple[PartnerWeight, ...]:
    _reject_when(
        not isinstance(partners_raw, list),
        f"{era_section}.partners must be a list",
    )

    partners: list[PartnerWeight] = []
    seen_partners: dict[str, int] = {}
    for partner_idx, partner_item_raw in enumerate(cast(list[object], partners_raw)):
        partner_section = f"{era_section}.partners[{partner_idx}]"
        partner_item = _require_dict(partner_item_raw, field=partner_section)
        require_keys(partner_section, partner_item, {"partner", "weight"})

        partner_name = _parse_name(partner_item["partner"], field=f"{partner_section}.partner")
        partner_key = partner_name.casefold()
        first_idx = seen_partners.get(partner_key, -1)
        _reject_when(
            first_idx >= 0,
            f"{era_section}.partners contains duplicate partner "
            f"'{partner_name}' at index {partner_idx} "
            f"(first seen at index {first_idx})",
        )
        seen_partners[partner_key] = partner_idx

        partners.append(
            PartnerWeight(
                partner=partner_name,
                weight=_parse_weight(partner_item["weight"], field=f"{partner_section}.weight"),
            )
        )

    _reject_when(
        bool(partners) and sum(entry.weight for entry in partners) <= 0,
        f"{era_section}.partners must sum to > 0",
    )
    return tuple(partners)


def _is_overlapping_or_unsorted(era_start: date, last_era_end: date | None) -> bool:
    return last_era_end is not None and era_start <= last_era_end


def _parse_eras(
    section: str, eras_raw: object, *, char_start: date, char_end: date
) -> tuple[PartnerEra, ...]:
    eras_input = _require_non_empty_list(eras_raw, field=f"{section}.eras")
    eras: list[PartnerEra] = []
    last_era_end: date | None = None
    for era_idx, era_entry_raw in enumerate(eras_input):
        era_section = f"{section}.eras[{era_idx}]"
        era_entry = _require_dict(era_entry_raw, field=era_section)
        require_keys(era_section, era_entry, {"date_start", "date_end", "partners"})

        era_start = _parse_iso_date(era_entry["date_start"], field=f"{era_section}.date_start")
        era_end = _parse_iso_date(era_entry["date_end"], field=f"{era_section}.date_end")
        _reject_when(era_start > era_end, f"{era_section} date_start must be <= date_end")
        _reject_when(
            era_start < char_start or era_end > char_end,
            f"{era_section} must be within parent character date range",
        )
        _reject_when(
            _is_overlapping_or_unsorted(era_start, last_era_end),
            f"{section}.eras has overlapping or unsorted ranges",
        )

        eras.append(
            PartnerEra(
                date_start=era_start,
                date_end=era_end,
                partners=_parse_partners(era_section, era_entry["partners"]),
            )
        )
        last_era_end = era_end
    return tuple(eras)


def _parse_character_distribution(
    idx: int,
    character_entry: object,
    *,
    known_characters: set[str],
    seen_characters: set[str],
    partner_distributions_key: str,
) -> CharacterPartnerDistribution:
    section = f"partner_distributions.{partner_distributions_key}[{idx}]"
    character_record = _require_dict(character_entry, field=section)
    require_keys(section, character_record, {"character", "date_start", "date_end", "eras"})

    character = _parse_name(character_record["character"], field=f"{section}.character")
    _reject_when(
        character not in known_characters,
        f"partner_distributions includes unknown character '{character}'",
    )
    _reject_when(
        character in seen_characters,
        f"partner_distributions includes duplicate character '{character}'",
    )
    seen_characters.add(character)

    char_start = _parse_iso_date(character_record["date_start"], field=f"{section}.date_start")
    char_end = _parse_iso_date(character_record["date_end"], field=f"{section}.date_end")
    _reject_when(char_start > char_end, f"{section} date_start must be <= date_end")

    return CharacterPartnerDistribution(
        character=character,
        date_start=char_start,
        date_end=char_end,
        eras=_parse_eras(
            section,
            character_record["eras"],
            char_start=char_start,
            char_end=char_end,
        ),
    )


def parse_partner_distribution_payload(
    partner_payload: dict[str, object],
    *,
    config_start: date,
    config_end: date,
    character_rows: list[tuple[str, date, date]],
    partner_distributions_key: str,
) -> PartnerDistributionDataset:
    require_keys(
        "partner_distributions",
        partner_payload,
        {
            "schema_version",
            "dataset_version",
            "date_start",
            "date_end",
            partner_distributions_key,
        },
    )
    schema_version = partner_payload["schema_version"]
    _reject_when(
        not isinstance(schema_version, int) or schema_version < 1,
        "partner_distributions.schema_version must be an integer >= 1",
    )

    dataset_version_raw = partner_payload["dataset_version"]
    _reject_when(
        not isinstance(dataset_version_raw, str) or not dataset_version_raw.strip(),
        "partner_distributions.dataset_version must be a non-empty string",
    )
    dataset_version = cast(str, dataset_version_raw).strip()

    payload_start = _parse_iso_date(
        partner_payload["date_start"], field="partner_distributions.date_start"
    )
    payload_end = _parse_iso_date(
        partner_payload["date_end"], field="partner_distributions.date_end"
    )

    _reject_when(
        payload_start > payload_end,
        "partner_distributions.date_start must be <= date_end",
    )
    _reject_when(
        payload_end < config_start or payload_start > config_end,
        "partner_distributions date range must overlap config.date_start/date_end",
    )

    entries = _require_non_empty_list(
        partner_payload[partner_distributions_key],
        field=f"partner_distributions.{partner_distributions_key}",
    )

    known_characters = {name for name, _, _ in character_rows}
    seen_characters: set[str] = set()
    by_character: dict[str, CharacterPartnerDistribution] = {}

    for idx, character_entry in enumerate(entries):
        distribution = _parse_character_distribution(
            idx,
            character_entry,
            known_characters=known_characters,
            seen_characters=seen_characters,
            partner_distributions_key=partner_distributions_key,
        )
        by_character[distribution.character] = distribution

    missing_characters = sorted(known_characters - seen_characters)
    _reject_when(
        bool(missing_characters),
        "partner_distributions is missing characters: " + ", ".join(missing_characters),
    )

    return PartnerDistributionDataset(
        schema_version=cast(int, schema_version),
        dataset_version=dataset_version,
        date_start=payload_start,
        date_end=payload_end,
        by_character=by_character,
    )
