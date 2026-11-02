"""The vouch graph, and the geohash the coarse area is built from."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed import build  # noqa: E402
from server.geo import PUBLIC_PRECISION, bounds, cell_centre, coarse, encode  # noqa: E402
from server.trust import DELTA, build_graph, connectors, describe, shortest_hops, trust  # noqa: E402


@pytest.fixture
def graph():
    _, _, vouches = build()
    return build_graph(vouches)


@pytest.fixture
def names():
    people, _, _ = build()
    return {person.id: person.display_name for person in people.values()}


# --- geohash ----------------------------------------------------------------

def test_encoding_matches_the_published_reference_values():
    assert encode(57.64911, 10.40744, 11) == "u4pruydqqvj"
    assert encode(42.6, -5.6, 5) == "ezs42"


def test_a_prefix_is_a_containing_cell():
    full = encode(33.2360, -96.8010, 12)
    for precision in range(1, 12):
        south, west, north, east = bounds(full[:precision])
        assert south <= 33.2360 <= north and west <= -96.8010 <= east
        longer = bounds(full[:precision + 1])
        assert south <= longer[0] and longer[2] <= north, "a longer prefix is a smaller cell"


def test_neighbours_in_the_same_cell_are_indistinguishable():
    """The mechanism: two addresses in one cell produce the same public value."""
    first = coarse(33.2360, -96.8010)
    second = coarse(33.2362, -96.8008)
    assert first == second
    assert cell_centre(first) == cell_centre(second)


def test_the_public_cell_is_about_a_kilometre():
    from server.geo import cell_size_metres
    height, width = cell_size_metres(coarse(33.2360, -96.8010))
    assert 400 < height < 800 and 800 < width < 1400
    assert PUBLIC_PRECISION == 6


def test_bad_input_is_refused():
    with pytest.raises(ValueError):
        encode(91.0, 0.0)
    with pytest.raises(ValueError):
        encode(0.0, 0.0, 99)
    with pytest.raises(ValueError):
        bounds("aio")  # a, i and o are not geohash characters


# --- trust ------------------------------------------------------------------

def test_vouches_are_directed(graph):
    assert shortest_hops(graph, "p00", "p01") == 1
    assert shortest_hops(graph, "p01", "p00") is None, "a vouch does not run both ways"


def test_trust_decays_with_distance(graph):
    assert trust(graph, "p00", "p01") == pytest.approx(DELTA)
    assert trust(graph, "p00", "p03") == pytest.approx(DELTA ** 2)
    assert trust(graph, "p00", "p00") == 1.0


def test_beyond_three_hops_is_a_stranger(graph):
    assert shortest_hops(graph, "p00", "p24") is None
    assert trust(graph, "p00", "p24") == 0.0


def test_only_first_hop_names_are_disclosed(graph, names):
    """A path names third parties, so only people the viewer vouched for are named."""
    two_hop = describe(graph, "p00", "p03", names)
    assert two_hop["hops"] == 2
    linking = connectors(graph, "p00", "p03")
    assert set(linking) <= set(graph["p00"]), "every named person is a direct vouch of the viewer"
    for person in linking:
        assert names[person] in two_hop["headline"]

    three_hop = describe(graph, "p00", "p08", names)
    assert three_hop["hops"] == 3
    for person_id, name in names.items():
        if person_id not in graph.get("p00", ()):
            assert name not in three_hop["headline"], f"{name} named without a direct vouch"


def test_a_stranger_is_described_without_blame(graph, names):
    described = describe(graph, "p00", "p24", names)
    assert described["hops"] is None
    assert "not a mark against them" in described["detail"]


def test_there_is_no_negative_vouch():
    _, _, vouches = build()
    assert all(getattr(v, "weight", 1) > 0 for v in vouches)
    assert not any(hasattr(v, "rating") or hasattr(v, "stars") for v in vouches)
