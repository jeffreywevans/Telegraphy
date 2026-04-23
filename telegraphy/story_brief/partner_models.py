from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, TypedDict


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

    def to_legacy_dict(self) -> dict[str, date | list[tuple[str, float]]]:
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

    def to_legacy_index(self) -> dict[str, list[dict[str, date | list[tuple[str, float]]]]]:
        return {
            character: [era.to_legacy_dict() for era in distribution.eras]
            for character, distribution in self.by_character.items()
        }


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

    try:
        payload_start = date.fromisoformat(str(partner_payload["date_start"]))
        payload_end = date.fromisoformat(str(partner_payload["date_end"]))
    except ValueError as exc:
        raise ValueError(
            "partner_distributions date_start/date_end must be ISO dates (YYYY-MM-DD)"
        ) from exc

    if payload_start > payload_end:
        raise ValueError("partner_distributions.date_start must be <= date_end")
    if payload_end < config_start or payload_start > config_end:
        raise ValueError("partner_distributions date range must overlap config.date_start/date_end")

    entries = partner_payload[partner_distributions_key]
    if not isinstance(entries, list) or not entries:
        raise ValueError(
            f"partner_distributions.{partner_distributions_key} "
            "must be a non-empty list"
        )

    known_characters = {name for name, _, _ in character_rows}
    seen_characters: set[str] = set()
    by_character: dict[str, CharacterPartnerDistribution] = {}

    for idx, character_entry in enumerate(entries):
        section = f"partner_distributions.{partner_distributions_key}[{idx}]"
        if not isinstance(character_entry, dict):
            raise ValueError(f"{section} must be an object")
        require_keys(section, character_entry, {"character", "date_start", "date_end", "eras"})

        character = str(character_entry["character"]).strip()
        if not character:
            raise ValueError(f"{section}.character must be a non-empty string")
        if character not in known_characters:
            raise ValueError(f"partner_distributions includes unknown character '{character}'")
        if character in seen_characters:
            raise ValueError(f"partner_distributions includes duplicate character '{character}'")
        seen_characters.add(character)

        try:
            char_start = date.fromisoformat(str(character_entry["date_start"]))
            char_end = date.fromisoformat(str(character_entry["date_end"]))
        except ValueError as exc:
            raise ValueError(
                f"{section} date_start/date_end must be ISO dates (YYYY-MM-DD)"
            ) from exc
        if char_start > char_end:
            raise ValueError(f"{section} date_start must be <= date_end")

        eras_raw = character_entry["eras"]
        if not isinstance(eras_raw, list) or not eras_raw:
            raise ValueError(f"{section}.eras must be a non-empty list")

        eras: list[PartnerEra] = []
        last_era_end: date | None = None
        for era_idx, era_entry in enumerate(eras_raw):
            era_section = f"{section}.eras[{era_idx}]"
            if not isinstance(era_entry, dict):
                raise ValueError(f"{era_section} must be an object")
            require_keys(era_section, era_entry, {"date_start", "date_end", "partners"})

            try:
                era_start = date.fromisoformat(str(era_entry["date_start"]))
                era_end = date.fromisoformat(str(era_entry["date_end"]))
            except ValueError as exc:
                raise ValueError(
                    f"{era_section} date_start/date_end must be ISO dates (YYYY-MM-DD)"
                ) from exc

            if era_start > era_end:
                raise ValueError(f"{era_section} date_start must be <= date_end")
            if era_start < char_start or era_end > char_end:
                raise ValueError(f"{era_section} must be within parent character date range")
            if last_era_end is not None and era_start <= last_era_end:
                raise ValueError(f"{section}.eras has overlapping or unsorted ranges")
            last_era_end = era_end

            partners_raw = era_entry["partners"]
            if not isinstance(partners_raw, list):
                raise ValueError(f"{era_section}.partners must be a list")

            partners: list[PartnerWeight] = []
            seen_partners: dict[str, int] = {}
            for partner_idx, partner_item in enumerate(partners_raw):
                partner_section = f"{era_section}.partners[{partner_idx}]"
                if not isinstance(partner_item, dict):
                    raise ValueError(f"{partner_section} must be an object")
                require_keys(partner_section, partner_item, {"partner", "weight"})

                partner_name = str(partner_item["partner"]).strip()
                if not partner_name:
                    raise ValueError(f"{partner_section}.partner must be a non-empty string")

                partner_key = partner_name.casefold()
                if partner_key in seen_partners:
                    first_idx = seen_partners[partner_key]
                    raise ValueError(
                        f"{era_section}.partners contains duplicate partner "
                        f"'{partner_name}' at index {partner_idx} "
                        f"(first seen at index {first_idx})"
                    )
                seen_partners[partner_key] = partner_idx

                weight_raw = partner_item["weight"]
                if isinstance(weight_raw, bool) or not isinstance(weight_raw, (int, float)):
                    raise ValueError(f"{partner_section}.weight must be a real number")
                if not math.isfinite(weight_raw) or weight_raw < 0:
                    raise ValueError(f"{partner_section}.weight must be finite and non-negative")

                partners.append(PartnerWeight(partner=partner_name, weight=float(weight_raw)))

            if partners and sum(entry.weight for entry in partners) <= 0:
                raise ValueError(f"{era_section}.partners must sum to > 0")

            eras.append(
                PartnerEra(
                    date_start=era_start,
                    date_end=era_end,
                    partners=tuple(partners),
                )
            )

        by_character[character] = CharacterPartnerDistribution(
            character=character,
            date_start=char_start,
            date_end=char_end,
            eras=tuple(eras),
        )

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
