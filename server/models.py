"""The data model, and the one place that decides which fields a viewer may see.

The central claim of this project is that an exact address cannot reach a
helper before the requester accepts them. That claim is not enforced by the
interface and not enforced by remembering to check. It is enforced here: a
response is built by copying an explicit list of field names for the reveal
level that has been computed, so a field that is not on the list has no path
into the payload at all. Adding a field to the model does not expose it.

tests/test_leaks.py walks every endpoint, every viewer and every stage and
asserts that no private value appears anywhere in the serialised output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable

from .geo import cell_centre, cell_size_metres, coarse


class Reveal(IntEnum):
    """How much of a request one viewer may see."""
    PUBLIC = 0   # category, coarse cell, time window
    OFFERED = 1  # the requester additionally sees who offered and why they are trusted
    ACCEPTED = 2  # the accepted helper additionally sees exact location and contact


class OfferState(str):
    OFFERED = "offered"
    ACCEPTED = "accepted"
    WITHDRAWN = "withdrawn"
    DECLINED = "declined"


@dataclass
class Person:
    id: str
    display_name: str
    # Private. Never serialised below Reveal.ACCEPTED, and only to the accepted helper.
    phone: str = ""
    joined: str = ""
    helped_count: int = 0


@dataclass
class Request:
    id: str
    requester_id: str
    category: str
    window: str
    latitude: float          # private, always
    longitude: float         # private, always
    address: str             # private until the requester accepts a helper
    details: str             # private until the requester accepts a helper
    created: str = ""
    cancelled: bool = False
    offers: list["Offer"] = field(default_factory=list)

    @property
    def coarse_cell(self) -> str:
        return coarse(self.latitude, self.longitude)

    def accepted_offer(self) -> "Offer | None":
        return next((o for o in self.offers if o.state == OfferState.ACCEPTED), None)

    def live_offers(self) -> list["Offer"]:
        return [o for o in self.offers if o.state in (OfferState.OFFERED, OfferState.ACCEPTED)]


@dataclass
class Offer:
    id: str
    request_id: str
    helper_id: str
    state: str = OfferState.OFFERED
    note: str = ""           # the helper's words to the requester, seen only by the requester


@dataclass
class Vouch:
    """Positive only, directed, and from a real prior interaction.

    There is no negative vouch and no rating. A person who needs a lot of help
    cannot accumulate a bad score for needing it, because there is no score.
    """
    from_id: str
    to_id: str
    basis: str = ""


# --- the field allowlists ----------------------------------------------------
# Each level lists exactly what may be copied out of a Request. These are the
# only field names any serialiser reads.
REQUEST_FIELDS: dict[Reveal, tuple[str, ...]] = {
    Reveal.PUBLIC: ("id", "category", "window", "created"),
    Reveal.OFFERED: ("id", "category", "window", "created"),
    Reveal.ACCEPTED: ("id", "category", "window", "created", "address", "details"),
}
PERSON_FIELDS: dict[Reveal, tuple[str, ...]] = {
    Reveal.PUBLIC: (),
    Reveal.OFFERED: ("id", "display_name", "joined", "helped_count"),
    Reveal.ACCEPTED: ("id", "display_name", "joined", "helped_count", "phone"),
}


def reveal_for(request: Request, viewer_id: str | None) -> Reveal:
    """What this viewer may see of this request. The only place levels are decided.

    The requester always sees their own request in full. A helper reaches
    ACCEPTED only through an offer of their own that the requester accepted.
    Everyone else, signed in or not, sees PUBLIC.
    """
    if viewer_id and viewer_id == request.requester_id:
        return Reveal.ACCEPTED
    accepted = request.accepted_offer()
    if viewer_id and accepted and accepted.helper_id == viewer_id:
        return Reveal.ACCEPTED
    return Reveal.PUBLIC


def serialise_request(request: Request, viewer_id: str | None, people: dict[str, Person]) -> dict:
    """Build a payload by copying only the allowed field names for this viewer."""
    level = reveal_for(request, viewer_id)
    payload = {name: getattr(request, name) for name in REQUEST_FIELDS[level]}
    cell = request.coarse_cell
    latitude, longitude = cell_centre(cell)
    height, width = cell_size_metres(cell)
    payload["area"] = {
        "cell": cell,
        "centre": {"latitude": round(latitude, 5), "longitude": round(longitude, 5)},
        "approximate_size_metres": [round(height), round(width)],
        "note": "Cell centre, not the address. Every point in this cell shares this value.",
    }
    payload["stage"] = int(level)
    payload["stage_name"] = level.name.lower()
    payload["offer_count"] = len(request.live_offers())
    payload["cancelled"] = request.cancelled

    is_requester = bool(viewer_id) and viewer_id == request.requester_id
    if is_requester:
        # Deliberate asymmetry: the person with less power sees who offered, first.
        payload["offers"] = [
            {
                "id": offer.id,
                "state": offer.state,
                "note": offer.note,
                "helper": {
                    name: getattr(people[offer.helper_id], name)
                    for name in PERSON_FIELDS[
                        Reveal.ACCEPTED if offer.state == OfferState.ACCEPTED else Reveal.OFFERED
                    ]
                },
            }
            for offer in request.offers
            if offer.state in (OfferState.OFFERED, OfferState.ACCEPTED)
        ]
    else:
        mine = [o for o in request.offers if viewer_id and o.helper_id == viewer_id]
        payload["my_offer"] = (
            {"id": mine[-1].id, "state": mine[-1].state} if mine else None
        )
        if level is Reveal.ACCEPTED:
            payload["requester"] = {
                name: getattr(people[request.requester_id], name)
                for name in PERSON_FIELDS[Reveal.ACCEPTED]
            }
    return payload


def private_values(requests: Iterable[Request], people: Iterable[Person]) -> set[str]:
    """Every value that must not appear in a payload that has not unlocked it.

    The leak test uses this so it does not need to know the model's shape: add a
    private field to the model, add it here, and the test covers it immediately.
    """
    values: set[str] = set()
    for request in requests:
        values.update({request.address, request.details,
                       f"{request.latitude}", f"{request.longitude}"})
    for person in people:
        values.add(person.phone)
    values.discard("")
    return values
