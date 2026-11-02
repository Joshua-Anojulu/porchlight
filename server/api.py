"""Porchlight API. In-memory, seeded, no accounts: a prototype of a protocol.

Sign-in is a person id passed as a query parameter. That is not authentication
and is not pretending to be: the project is about what a protocol discloses,
and bolting on a login would add no evidence for that claim. The README says so.
"""
from __future__ import annotations

import sys
from itertools import count
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed import build  # noqa: E402
from server import stages  # noqa: E402
from server.models import (  # noqa: E402
    OfferState, Person, Request, Reveal, reveal_for, serialise_request,
)
from server.trust import build_graph, describe  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title="Porchlight", version="1.0.0",
              description="A prototype of a staged-disclosure protocol for neighbourhood help.")

PEOPLE: dict[str, Person] = {}
REQUESTS: dict[str, Request] = {}
VOUCHES: list = []
GRAPH: dict[str, set[str]] = {}
_ids = count(100)


def reset() -> None:
    global PEOPLE, REQUESTS, VOUCHES, GRAPH
    PEOPLE, REQUESTS, VOUCHES = build()
    GRAPH = build_graph(VOUCHES)


reset()


def _person(person_id: str | None) -> str | None:
    if person_id in (None, "", "anonymous"):
        return None
    if person_id not in PEOPLE:
        raise HTTPException(404, f"No such person: {person_id}")
    return person_id


def _request(request_id: str) -> Request:
    if request_id not in REQUESTS:
        raise HTTPException(404, "No such request.")
    return REQUESTS[request_id]


def _guard(action) -> dict:
    try:
        action()
    except stages.TransitionError as error:
        raise HTTPException(409, str(error)) from error
    return {"ok": True}


class NewRequest(BaseModel):
    requester_id: str
    category: str = Field(max_length=80)
    window: str = Field(max_length=80)
    latitude: float
    longitude: float
    address: str = Field(max_length=200)
    details: str = Field(default="", max_length=800)


class NewOffer(BaseModel):
    helper_id: str
    note: str = Field(default="", max_length=500)


@app.get("/api/people")
def people() -> dict:
    """Display names only, so the account switcher in the demo has labels."""
    return {"people": [{"id": p.id, "display_name": p.display_name} for p in PEOPLE.values()]}


@app.get("/api/requests")
def board(viewer: str | None = Query(default=None)) -> dict:
    """The public board. Every payload here is built at the viewer's reveal level."""
    viewer_id = _person(viewer)
    live = [r for r in REQUESTS.values() if not r.cancelled]
    return {
        "viewer": viewer_id,
        "requests": [serialise_request(r, viewer_id, PEOPLE) for r in
                     sorted(live, key=lambda r: r.created, reverse=True)],
    }


@app.get("/api/requests/{request_id}")
def one(request_id: str, viewer: str | None = Query(default=None)) -> dict:
    request = _request(request_id)
    viewer_id = _person(viewer)
    payload = serialise_request(request, viewer_id, PEOPLE)
    if viewer_id == request.requester_id:
        # The requester, and only the requester, is told why each helper is trusted.
        names = {person.id: person.display_name for person in PEOPLE.values()}
        for entry in payload.get("offers", []):
            entry["trust"] = describe(GRAPH, viewer_id, entry["helper"]["id"], names)
    return payload


@app.post("/api/requests")
def post_request(body: NewRequest) -> dict:
    _person(body.requester_id)
    request_id = f"r{next(_ids)}"
    REQUESTS[request_id] = Request(
        id=request_id, requester_id=body.requester_id, category=body.category,
        window=body.window, latitude=body.latitude, longitude=body.longitude,
        address=body.address, details=body.details, created="2026-11-30",
    )
    return serialise_request(REQUESTS[request_id], body.requester_id, PEOPLE)


@app.post("/api/requests/{request_id}/offers")
def make_offer(request_id: str, body: NewOffer) -> dict:
    request = _request(request_id)
    _person(body.helper_id)
    try:
        made = stages.offer(request, body.helper_id, f"o{next(_ids)}", body.note)
    except stages.TransitionError as error:
        raise HTTPException(409, str(error)) from error
    return {"id": made.id, "state": made.state}


@app.post("/api/requests/{request_id}/offers/{offer_id}/accept")
def accept_offer(request_id: str, offer_id: str, actor: str = Query(...)) -> dict:
    request = _request(request_id)
    return _guard(lambda: stages.accept(request, offer_id, _person(actor)))


@app.post("/api/requests/{request_id}/offers/{offer_id}/decline")
def decline_offer(request_id: str, offer_id: str, actor: str = Query(...)) -> dict:
    request = _request(request_id)
    return _guard(lambda: stages.decline(request, offer_id, _person(actor)))


@app.post("/api/requests/{request_id}/offers/{offer_id}/withdraw")
def withdraw_offer(request_id: str, offer_id: str, actor: str = Query(...)) -> dict:
    request = _request(request_id)
    return _guard(lambda: stages.withdraw(request, offer_id, _person(actor)))


@app.post("/api/requests/{request_id}/cancel")
def cancel_request(request_id: str, actor: str = Query(...)) -> dict:
    request = _request(request_id)
    return _guard(lambda: stages.cancel(request, _person(actor)))


@app.post("/api/reset")
def reset_demo() -> dict:
    reset()
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
