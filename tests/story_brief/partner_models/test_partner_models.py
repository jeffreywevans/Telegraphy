import hashlib
from copy import deepcopy
from datetime import date, timedelta
from typing import Callable

import pytest

from telegraphy.story_brief.partner_models import (
    CharacterPartnerDistribution,
    PartnerDistributionDataset,
    PartnerEra,
    _parse_character_distribution,
    _parse_eras,
    _parse_partners,
    parse_partner_distribution_payload,
)


def _build_partner_payload(partner_payload_factory) -> dict[str, object]:
    return partner_payload_factory(
        alex_eras=[
            {
                "date_start": "2000-01-01",
                "date_end": "2000-06-30",
                "partners": [{"partner": "Jordan", "weight": 1.0}],
            },
            {
                "date_start": "2000-07-01",
                "date_end": "2000-12-31",
                "partners": [],
            },
        ],
        jordan_eras=[
            {
                "date_start": "2000-01-01",
                "date_end": "2000-12-31",
                "partners": [{"partner": "Alex", "weight": 1.0}],
            }
        ],
    )


def _parse_payload(
    payload: dict[str, object], partner_character_rows: list[tuple[str, date, date]]
):
    return parse_partner_distribution_payload(
        payload,
        config_start=date(2000, 1, 1),
        config_end=date(2000, 12, 31),
        character_rows=partner_character_rows,
        partner_distributions_key="partner_distributions",
    )


def _mutate_duplicate_partners(payload: dict[str, object]) -> None:
    entries = payload["partner_distributions"]
    entries[0]["eras"][0]["partners"] = [
        {"partner": "Jordan", "weight": 0.7},
        {"partner": "jordan", "weight": 0.3},
    ]


def _mutate_non_object_entry(payload: dict[str, object]) -> None:
    payload["partner_distributions"] = ["bad-entry"]


def _mutate_overlapping_eras(payload: dict[str, object]) -> None:
    entries = payload["partner_distributions"]
    entries[0]["eras"] = [
        {
            "date_start": "2000-01-01",
            "date_end": "2000-06-30",
            "partners": [{"partner": "Jordan", "weight": 1.0}],
        },
        {
            "date_start": "2000-06-30",
            "date_end": "2000-12-31",
            "partners": [{"partner": "Jordan", "weight": 1.0}],
        },
    ]


def _mutate_invalid_calendar_date(payload: dict[str, object]) -> None:
    entries = payload["partner_distributions"]
    entries[0]["date_start"] = "2000-02-30"


def test_parse_partner_distribution_payload_returns_typed_dataset(
    partner_payload_factory,
    partner_character_rows,
) -> None:
    dataset = _parse_payload(
        _build_partner_payload(partner_payload_factory), partner_character_rows
    )

    assert isinstance(dataset, PartnerDistributionDataset)
    assert set(dataset.by_character) == {"Alex", "Jordan"}

    alex = dataset.by_character["Alex"]
    assert isinstance(alex, CharacterPartnerDistribution)
    assert len(alex.eras) == 2
    assert isinstance(alex.eras[0], PartnerEra)
    assert alex.eras[0].covers(date(2000, 3, 1))
    assert not alex.eras[0].covers(date(2000, 7, 1))


def test_parse_partner_distribution_payload_parses_partner_eras(
    partner_payload_factory,
    partner_character_rows,
) -> None:
    dataset = _parse_payload(
        _build_partner_payload(partner_payload_factory), partner_character_rows
    )

    alex_eras = dataset.by_character["Alex"].eras
    assert alex_eras[0].date_start == date(2000, 1, 1)
    assert alex_eras[0].partners[0].partner == "Jordan"
    assert alex_eras[0].partners[0].weight == 1.0
    assert alex_eras[1].partners == ()


def test_parse_partners_rejects_case_insensitive_duplicates() -> None:
    with pytest.raises(ValueError, match="contains duplicate partner"):
        _parse_partners(
            "partner_distributions.partner_distributions[0].eras[0]",
            [
                {"partner": "Jordan", "weight": 0.7},
                {"partner": "jordan", "weight": 0.3},
            ],
        )


def test_parse_eras_rejects_range_outside_parent_character() -> None:
    with pytest.raises(ValueError, match="must be within parent character date range"):
        _parse_eras(
            "partner_distributions.partner_distributions[0]",
            [
                {
                    "date_start": "1999-12-31",
                    "date_end": "2000-01-01",
                    "partners": [{"partner": "Jordan", "weight": 1.0}],
                }
            ],
            char_start=date(2000, 1, 1),
            char_end=date(2000, 12, 31),
        )


def test_parse_character_distribution_uses_partner_distribution_key_in_path() -> None:
    with pytest.raises(ValueError, match=r"partner_distributions\.entries\[0\] must be an object"):
        _parse_character_distribution(
            0,
            "bad-entry",
            known_characters={"Alex"},
            seen_characters=set(),
            partner_distributions_key="entries",
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (_mutate_duplicate_partners, "contains duplicate partner"),
        (_mutate_non_object_entry, "must be an object"),
        (_mutate_overlapping_eras, "overlapping or unsorted ranges"),
        (_mutate_invalid_calendar_date, "must be an ISO date"),
    ],
)
def test_parse_partner_distribution_payload_rejects_invalid_shapes(
    mutator: Callable[[dict[str, object]], None],
    message: str,
    partner_payload_factory,
    partner_character_rows,
) -> None:
    payload = deepcopy(_build_partner_payload(partner_payload_factory))
    mutator(payload)

    with pytest.raises(ValueError, match=message):
        _parse_payload(payload, partner_character_rows)


def _build_payload_with_eras(
    alex_eras: list[dict[str, object]],
    jordan_eras: list[dict[str, object]],
    *,
    start_date: str = "2000-01-01",
    end_date: str = "2000-12-31",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "dataset_version": "test-dataset",
        "date_start": start_date,
        "date_end": end_date,
        "partner_distributions": [
            {
                "character": "Alex",
                "date_start": start_date,
                "date_end": end_date,
                "eras": alex_eras,
            },
            {
                "character": "Jordan",
                "date_start": start_date,
                "date_end": end_date,
                "eras": jordan_eras,
            },
        ],
    }


def _seeded_int(seed: int, counter: int, low: int, high: int) -> int:
    if low > high:
        raise ValueError("low must be <= high")
    span = (high - low) + 1
    digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
    offset = int.from_bytes(digest[:8], "big") % span
    return low + offset


def _seeded_float(seed: int, counter: int, low: float, high: float) -> float:
    if low > high:
        raise ValueError("low must be <= high")
    digest = hashlib.sha256(f"{seed}:{counter}:float".encode("utf-8")).digest()
    ratio = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
    return low + ((high - low) * ratio)


def _stable_sort_key(seed: int, label: str, value: int) -> bytes:
    return hashlib.sha256(f"{seed}:{label}:{value}".encode("utf-8")).digest()


def _build_cut_points(seed: int, all_days: int, min_cuts: int, max_cuts: int) -> list[int]:
    cut_count = _seeded_int(seed, 0, min_cuts, max_cuts)
    cut_count = min(cut_count, all_days - 1)
    ranked_days = sorted(
        range(1, all_days),
        key=lambda day: _stable_sort_key(seed, "cuts", day),
    )
    boundaries = ranked_days[:cut_count]
    return [0, *sorted(boundaries), all_days]


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(30))
def test_parse_partner_distribution_payload_randomized_era_boundaries_cover_every_day(
    seed: int,
) -> None:
    start = date(2000, 1, 1)
    end = date(2000, 12, 31)
    all_days = (end - start).days + 1

    cut_points = _build_cut_points(seed, all_days, min_cuts=1, max_cuts=8)

    alex_eras: list[dict[str, object]] = []
    jordan_eras: list[dict[str, object]] = []
    for left, right in zip(cut_points, cut_points[1:], strict=False):
        era_start = start + timedelta(days=left)
        era_end = start + timedelta(days=right - 1)
        alex_eras.append(
            {
                "date_start": era_start.isoformat(),
                "date_end": era_end.isoformat(),
                "partners": [{"partner": "Jordan", "weight": 1.0}],
            }
        )
        jordan_eras.append(
            {
                "date_start": era_start.isoformat(),
                "date_end": era_end.isoformat(),
                "partners": [{"partner": "Alex", "weight": 1.0}],
            }
        )

    dataset = parse_partner_distribution_payload(
        _build_payload_with_eras(
            alex_eras,
            jordan_eras,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        ),
        config_start=start,
        config_end=end,
        character_rows=[("Alex", start, end), ("Jordan", start, end)],
        partner_distributions_key="partner_distributions",
    )

    for offset in range(all_days):
        day = start + timedelta(days=offset)
        alex_covering = [era for era in dataset.by_character["Alex"].eras if era.covers(day)]
        jordan_covering = [era for era in dataset.by_character["Jordan"].eras if era.covers(day)]
        assert len(alex_covering) == 1
        assert len(jordan_covering) == 1


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(20))
def test_parse_partner_distribution_payload_rejects_randomized_casefold_duplicates(
    seed: int,
) -> None:
    start = date(2000, 1, 1)
    end = date(2000, 12, 31)
    mask = [
        str.upper if _seeded_int(seed, idx, 0, 1) else str.lower
        for idx, _ in enumerate("Jordan")
    ]
    variant = "".join(transform(char) for transform, char in zip(mask, "Jordan", strict=True))
    if variant == "Jordan":
        variant = "jORDAN"

    payload = _build_payload_with_eras(
        [
            {
                "date_start": "2000-01-01",
                "date_end": "2000-12-31",
                "partners": [
                    {"partner": "Jordan", "weight": 0.5},
                    {"partner": variant, "weight": 0.5},
                ],
            }
        ],
        [
            {
                "date_start": "2000-01-01",
                "date_end": "2000-12-31",
                "partners": [{"partner": "Alex", "weight": 1.0}],
            }
        ],
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

    with pytest.raises(ValueError, match="contains duplicate partner"):
        parse_partner_distribution_payload(
            payload,
            config_start=start,
            config_end=end,
            character_rows=[("Alex", start, end), ("Jordan", start, end)],
            partner_distributions_key="partner_distributions",
        )


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(20))
def test_parse_partner_distribution_payload_zero_weight_property_cases(seed: int) -> None:
    start = date(2000, 1, 1)
    end = date(2000, 12, 31)
    length = _seeded_int(seed, 0, 1, 5)
    payload = _build_payload_with_eras(
        [
            {
                "date_start": "2000-01-01",
                "date_end": "2000-12-31",
                "partners": [{"partner": f"Jordan-{idx}", "weight": 0.0} for idx in range(length)],
            }
        ],
        [{"date_start": "2000-01-01", "date_end": "2000-12-31", "partners": []}],
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

    with pytest.raises(ValueError, match="must sum to > 0"):
        parse_partner_distribution_payload(
            payload,
            config_start=start,
            config_end=end,
            character_rows=[("Alex", start, end), ("Jordan", start, end)],
            partner_distributions_key="partner_distributions",
        )


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(20))
def test_parse_partner_distribution_payload_randomized_reciprocal_partner_weights_round_trip(
    seed: int,
) -> None:
    start = date(2000, 1, 1)
    end = date(2000, 12, 31)
    all_days = (end - start).days + 1

    cut_points = _build_cut_points(seed + 100, all_days, min_cuts=1, max_cuts=6)

    alex_eras: list[dict[str, object]] = []
    jordan_eras: list[dict[str, object]] = []
    expected_alex_weights: list[float] = []
    expected_jordan_weights: list[float] = []
    for left, right in zip(cut_points, cut_points[1:], strict=False):
        era_start = start + timedelta(days=left)
        era_end = start + timedelta(days=right - 1)
        alex_weight = round(_seeded_float(seed, left + right, 0.1, 5.0), 3)
        jordan_weight = round(_seeded_float(seed + 1_000, left + right, 0.1, 5.0), 3)
        expected_alex_weights.append(alex_weight)
        expected_jordan_weights.append(jordan_weight)
        alex_eras.append(
            {
                "date_start": era_start.isoformat(),
                "date_end": era_end.isoformat(),
                "partners": [{"partner": "Jordan", "weight": alex_weight}],
            }
        )
        jordan_eras.append(
            {
                "date_start": era_start.isoformat(),
                "date_end": era_end.isoformat(),
                "partners": [{"partner": "Alex", "weight": jordan_weight}],
            }
        )

    dataset = parse_partner_distribution_payload(
        _build_payload_with_eras(
            alex_eras,
            jordan_eras,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        ),
        config_start=start,
        config_end=end,
        character_rows=[("Alex", start, end), ("Jordan", start, end)],
        partner_distributions_key="partner_distributions",
    )
    alex_dataset_eras = dataset.by_character["Alex"].eras
    jordan_dataset_eras = dataset.by_character["Jordan"].eras
    assert len(alex_dataset_eras) == len(alex_eras)
    assert len(jordan_dataset_eras) == len(jordan_eras)
    for idx in range(len(alex_eras)):
        assert alex_dataset_eras[idx].date_start == jordan_dataset_eras[idx].date_start
        assert alex_dataset_eras[idx].date_end == jordan_dataset_eras[idx].date_end
        assert alex_dataset_eras[idx].partners[0].partner == "Jordan"
        assert jordan_dataset_eras[idx].partners[0].partner == "Alex"
        assert alex_dataset_eras[idx].partners[0].weight == expected_alex_weights[idx]
        assert jordan_dataset_eras[idx].partners[0].weight == expected_jordan_weights[idx]
