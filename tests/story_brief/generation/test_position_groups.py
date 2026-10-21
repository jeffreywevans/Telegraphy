from __future__ import annotations

import json
import random
from pathlib import Path
from typing import cast

import pytest

from telegraphy.story_brief.data_io import get_data, get_normalized_story_data
from telegraphy.story_brief.generation import pick_tags_from_selected_groups
from telegraphy.story_brief.normalization import _build_story_data
from telegraphy.story_brief.position_groups import normalize_position_groups
from telegraphy.story_brief.story_data import StoryData


@pytest.mark.parametrize(
    "name",
    [
        "69",
        "amazon",
        "bodyguard",
        "butterfly",
        "cowgirl",
        "cunnilingus",
        "doggy_style",
        "fellatio",
        "guard",
        "lapdance",
        "lotus",
        "missionary",
        "rodeo",
        "scissors",
        "sinner",
        "spoons",
    ],
)
def test_position_group_selection_uses_weight_then_uniform_variants(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = get_normalized_story_data()
    groups = data["position_groups"]
    names = sorted(groups)
    lower = sum(groups[n]["weight"] for n in names[: names.index(name)])
    rng = random.Random(1)
    monkeypatch.setattr(rng, "random", lambda: (lower + groups[name]["weight"] / 2) / 100)
    seen: list[tuple[str, ...]] = []

    def choose(variants: tuple[str, ...]) -> str:
        seen.append(variants)
        return variants[-1]

    monkeypatch.setattr(rng, "choice", choose)
    assert pick_tags_from_selected_groups(rng, ["position"], data) == [groups[name]["variants"][-1]]
    assert seen == [groups[name]["variants"]]


def test_packaged_positions_are_sorted_and_total_100_percent() -> None:
    raw = get_data()["config"]["sexual_scene_tag_groups"]["position"]
    assert list(raw) == sorted(raw)
    assert len(raw) == 16
    assert sum(entry["weight"] for entry in raw.values()) == 100
    assert sum(len(entry["variants"]) for entry in raw.values()) == 59
    for entry in raw.values():
        assert entry["variants"] == sorted(entry["variants"])


@pytest.mark.parametrize(
    "raw,message",
    [
        (None, "non-empty object"),
        ({}, "non-empty object"),
        ({"": {"weight": 2, "variants": ["a"]}}, "names must be non-empty"),
        ({"a": []}, "expected weight and variants"),
        ({"a": {"weight": True, "variants": ["a"]}}, "weight must be between"),
        ({"a": {"weight": "2", "variants": ["a"]}}, "weight must be between"),
        ({"a": {"weight": float("nan"), "variants": ["a"]}}, "weight must be between"),
        ({"a": {"weight": 0, "variants": ["a"]}}, "weight must be between"),
        ({"a": {"weight": 33, "variants": ["a"]}}, "weight must be between"),
        ({"a": {"weight": 2, "variants": []}}, "non-empty string list"),
        ({"a": {"weight": 2, "variants": "a"}}, "non-empty string list"),
        ({"a": {"weight": 2, "variants": [1]}}, "non-empty string list"),
        ({"a": {"weight": 2, "variants": ["a", "a"]}}, "duplicate variants"),
        ({"a": {"weight": 2, "variants": ["a"]}}, "total 100 percent"),
    ],
)
def test_invalid_position_groups_are_rejected(raw: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_position_groups(raw)


def test_position_order_does_not_change_seeded_selection() -> None:
    data = get_normalized_story_data()
    reordered = cast(StoryData, dict(data))
    reordered["position_groups"] = dict(reversed(list(data["position_groups"].items())))
    for seed in range(20):
        assert pick_tags_from_selected_groups(random.Random(seed), ["position"], data) == (
            pick_tags_from_selected_groups(random.Random(seed), ["position"], reordered)
        )


def test_invalid_position_groups_are_rejected_when_loading_dataset(
    cli_dataset_factory,
) -> None:
    dataset: Path = cli_dataset_factory("invalid-position-weights")
    path = dataset / "sexual_scene_tags.json"
    raw = json.loads(path.read_text())
    raw["sexual_scene_tag_groups"]["position"]["missionary"]["weight"] = 31
    path.write_text(json.dumps(raw))
    from telegraphy.story_brief.data_io import load_data

    payloads = load_data(dataset)
    with pytest.raises(ValueError, match="total 100 percent"):
        _build_story_data(payloads)
