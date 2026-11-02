"""Trust as a path through a vouch graph, rendered in words rather than a number.

Why no ratings. A rating system scores people on how they behave, and in mutual
aid the people being scored most are the people asking for help. Someone who
needs help often accumulates a bad score for needing it, which is precisely
backwards. So there is no score, no stars, and no negative vouch. There is only
a directed, positive claim: this person vouches for that one.

Trust between two people is the best path through that graph, decayed by its
length: T = delta ** hops, with delta 0.6 and at most 3 hops. A neighbour you
vouched for reads 0.6, a friend of theirs 0.36, and anyone further is a
stranger. BFS from the viewer is enough; the graph is a neighbourhood.

What the viewer is told is not the number, and not the path. A path names third
parties and who vouched for whom, which is private information about people who
are not party to this request. So the renderer names only people the viewer has
vouched for directly, and anything further is summarised by count.
"""
from __future__ import annotations

from collections import deque

DELTA = 0.6
MAX_HOPS = 3


def build_graph(vouches) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for vouch in vouches:
        graph.setdefault(vouch.from_id, set()).add(vouch.to_id)
    return graph


def shortest_hops(graph: dict[str, set[str]], source: str, target: str,
                  max_hops: int = MAX_HOPS) -> int | None:
    """Fewest vouch hops from source to target, or None beyond the cap."""
    if source == target:
        return 0
    seen = {source}
    queue = deque([(source, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbour in graph.get(node, ()):  # directed: A vouching for B is not B for A
            if neighbour == target:
                return depth + 1
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append((neighbour, depth + 1))
    return None


def trust(graph: dict[str, set[str]], source: str, target: str) -> float:
    hops = shortest_hops(graph, source, target)
    return 0.0 if hops is None else DELTA ** hops


def connectors(graph: dict[str, set[str]], source: str, target: str) -> list[str]:
    """People the viewer vouched for directly who vouch for the target.

    Only first-hop names are returned. Naming anyone further would disclose a
    vouch between two other people to someone who is party to neither.
    """
    return sorted(person for person in graph.get(source, ()) if target in graph.get(person, ()))


def describe(graph: dict[str, set[str]], source: str, target: str, names: dict[str, str]) -> dict:
    """What the requester is shown about a helper who offered.

    Returns words, plus the hop count so the interface can style it. The trust
    number itself is never rendered to a user: "vouched for by someone you
    trust" is actionable and "trust 0.36" is not.
    """
    hops = shortest_hops(graph, source, target)
    if hops is None:
        return {
            "hops": None,
            "headline": "No one you have vouched for vouches for them",
            "detail": "They are a stranger to your part of the network. That is not a mark against them; it means this connection carries no information.",
        }
    if hops == 1:
        return {
            "hops": 1,
            "headline": "You have vouched for them",
            "detail": "You recorded this vouch yourself after a previous exchange.",
        }
    if hops == 2:
        linking = connectors(graph, source, target)
        named = ", ".join(names.get(person, person) for person in linking[:2])
        more = len(linking) - 2
        return {
            "hops": 2,
            "headline": f"Vouched for by {named}" + (f" and {more} other{'s' if more > 1 else ''} you trust" if more > 0 else ""),
            "detail": "You vouched for them, and they vouched for this helper.",
        }
    return {
        "hops": hops,
        "headline": f"Connected through {hops - 1} neighbours you trust",
        "detail": "The people in between are not named, because who vouched for whom is their business, not part of this request.",
    }
