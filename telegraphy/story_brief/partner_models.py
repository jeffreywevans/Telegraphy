from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, TypeAlias, TypedDict


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


def require_keys(
    section_name: str, payload: dict[str, object], required: AbstractSet[str]
) -> None:
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"{section_name}: missing required keys: {', '.join(missing)}")


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
    if not parsed:
        raise ValueError(f"{field} must be a non-empty string")
    return parsed


def _parse_weight(raw: object, *, field: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{field} must be a real number")
    if not math.isfinite(raw) or raw < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return float(raw)


def _require_non_empty_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return value


def _parse_partners(era_section: str, partners_raw: object) -> tuple[PartnerWeight, ...]:
    if not isinstance(partners_raw, list):
        raise ValueError(f"{era_section}.partners must be a list")

    partners: list[PartnerWeight] = []
    seen_partners: dict[str, int] = {}
    for partner_idx, partner_item in enumerate(partners_raw):
        partner_section = f"{era_section}.partners[{partner_idx}]"
        if not isinstance(partner_item, dict):
            raise ValueError(f"{partner_section} must be an object")
        require_keys(partner_section, partner_item, {"partner", "weight"})

        partner_name = _parse_name(partner_item["partner"], field=f"{partner_section}.partner")
        partner_key = partner_name.casefold()
        if partner_key in seen_partners:
            first_idx = seen_partners[partner_key]
            raise ValueError(
                f"{era_section}.partners contains duplicate partner "
                f"'{partner_name}' at index {partner_idx} "
                f"(first seen at index {first_idx})"
            )
        seen_partners[partner_key] = partner_idx

        partners.append(
            PartnerWeight(
                partner=partner_name,
                weight=_parse_weight(partner_item["weight"], field=f"{partner_section}.weight"),
            )
        )

    if partners and sum(entry.weight for entry in partners) <= 0:
        raise ValueError(f"{era_section}.partners must sum to > 0")

    return tuple(partners)


def _parse_eras(
    section: str, eras_raw: object, *, char_start: date, char_end: date
) -> tuple[PartnerEra, ...]:
    eras_input = _require_non_empty_list(eras_raw, field=f"{section}.eras")
    eras: list[PartnerEra] = []
    last_era_end: date | None = None
    for era_idx, era_entry in enumerate(eras_input):
        era_section = f"{section}.eras[{era_idx}]"
        if not isinstance(era_entry, dict):
            raise ValueError(f"{era_section} must be an object")
        require_keys(era_section, era_entry, {"date_start", "date_end", "partners"})

        era_start = _parse_iso_date(era_entry["date_start"], field=f"{era_section}.date_start")
        era_end = _parse_iso_date(era_entry["date_end"], field=f"{era_section}.date_end")
        if era_start > era_end:
            raise ValueError(f"{era_section} date_start must be <= date_end")
        if era_start < char_start or era_end > char_end:
            raise ValueError(f"{era_section} must be within parent character date range")
        if last_era_end is not None and era_start <= last_era_end:
            raise ValueError(f"{section}.eras has overlapping or unsorted ranges")

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
    if not isinstance(character_entry, dict):
        raise ValueError(f"{section} must be an object")
    require_keys(section, character_entry, {"character", "date_start", "date_end", "eras"})

    character = _parse_name(character_entry["character"], field=f"{section}.character")
    if character not in known_characters:
        raise ValueError(f"partner_distributions includes unknown character '{character}'")
    if character in seen_characters:
        raise ValueError(f"partner_distributions includes duplicate character '{character}'")
    seen_characters.add(character)

    char_start = _parse_iso_date(character_entry["date_start"], field=f"{section}.date_start")
    char_end = _parse_iso_date(character_entry["date_end"], field=f"{section}.date_end")
    if char_start > char_end:
        raise ValueError(f"{section} date_start must be <= date_end")

    return CharacterPartnerDistribution(
        character=character,
        date_start=char_start,
        date_end=char_end,
        eras=_parse_eras(
            section,
            character_entry["eras"],
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
    if not isinstance(schema_version, int) or schema_version < 1:
        raise ValueError("partner_distributions.schema_version must be an integer >= 1")

    dataset_version_raw = partner_payload["dataset_version"]
    if not isinstance(dataset_version_raw, str) or not dataset_version_raw.strip():
        raise ValueError("partner_distributions.dataset_version must be a non-empty string")
    dataset_version = dataset_version_raw.strip()

    payload_start = _parse_iso_date(
        partner_payload["date_start"], field="partner_distributions.date_start"
    )
    payload_end = _parse_iso_date(
        partner_payload["date_end"], field="partner_distributions.date_end"
    )

    if payload_start > payload_end:
        raise ValueError("partner_distributions.date_start must be <= date_end")
    if payload_end < config_start or payload_start > config_end:
        raise ValueError("partner_distributions date range must overlap config.date_start/date_end")

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
    if missing_characters:
        raise ValueError(
            "partner_distributions is missing characters: "
            + ", ".join(missing_characters)
        )

    return PartnerDistributionDataset(
        schema_version=schema_version,
        dataset_version=dataset_version,
        date_start=payload_start,
        date_end=payload_end,
        by_character=by_character,
    )
