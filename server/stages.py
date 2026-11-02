"""The state machine, with every transition guarded.

Rules, in one place so they can be read in one sitting:

  post      anyone may post a request for themselves
  offer     anyone except the requester may offer, once, while the request is
            open and nothing has been accepted
  withdraw  a helper may withdraw their own offer at any time before it is
            accepted, and nothing they did is revealed
  decline   the requester may decline an offer
  accept    only the requester, only one offer, only while it is still offered.
            This is the transition that unlocks the address, so it is the one
            with the most guards
  cancel    only the requester, and it re-closes anything already unlocked

Every refusal raises TransitionError with a reason a person could read. The
tests assert the failure of every illegal transition rather than the success of
the legal ones, because a protocol is only worth as much as what it refuses.
"""
from __future__ import annotations

from .models import Offer, OfferState, Request


class TransitionError(Exception):
    """An illegal transition. Carries a reason fit to show a user."""


def _open(request: Request) -> None:
    if request.cancelled:
        raise TransitionError("This request was cancelled.")


def may_offer(request: Request, helper_id: str) -> None:
    _open(request)
    if helper_id == request.requester_id:
        raise TransitionError("You cannot offer to help with your own request.")
    if request.accepted_offer():
        raise TransitionError("Someone has already been accepted for this request.")
    if any(o.helper_id == helper_id and o.state == OfferState.OFFERED for o in request.offers):
        raise TransitionError("You have already offered. The requester decides next.")


def offer(request: Request, helper_id: str, offer_id: str, note: str = "") -> Offer:
    may_offer(request, helper_id)
    made = Offer(id=offer_id, request_id=request.id, helper_id=helper_id, note=note[:500])
    request.offers.append(made)
    return made


def _find(request: Request, offer_id: str) -> Offer:
    found = next((o for o in request.offers if o.id == offer_id), None)
    if found is None:
        raise TransitionError("No such offer on this request.")
    return found


def may_accept(request: Request, offer_id: str, actor_id: str) -> Offer:
    _open(request)
    if actor_id != request.requester_id:
        raise TransitionError("Only the person who asked can accept an offer.")
    if request.accepted_offer():
        raise TransitionError("You have already accepted someone for this request.")
    chosen = _find(request, offer_id)
    if chosen.state != OfferState.OFFERED:
        raise TransitionError(f"That offer is {chosen.state} and cannot be accepted.")
    return chosen


def accept(request: Request, offer_id: str, actor_id: str) -> Offer:
    """The transition that unlocks the address, and the only one that does."""
    chosen = may_accept(request, offer_id, actor_id)
    chosen.state = OfferState.ACCEPTED
    # Every other live offer is declined, so no one else is left with a pending
    # claim on a request that is now settled.
    for other in request.offers:
        if other is not chosen and other.state == OfferState.OFFERED:
            other.state = OfferState.DECLINED
    return chosen


def withdraw(request: Request, offer_id: str, actor_id: str) -> Offer:
    chosen = _find(request, offer_id)
    if chosen.helper_id != actor_id:
        raise TransitionError("Only the helper who made an offer can withdraw it.")
    if chosen.state in (OfferState.WITHDRAWN, OfferState.DECLINED):
        raise TransitionError(f"That offer is already {chosen.state}.")
    # Withdrawing after acceptance re-locks the address: the reveal level is
    # computed from state, so nothing has to be scrubbed.
    chosen.state = OfferState.WITHDRAWN
    return chosen


def decline(request: Request, offer_id: str, actor_id: str) -> Offer:
    if actor_id != request.requester_id:
        raise TransitionError("Only the person who asked can decline an offer.")
    chosen = _find(request, offer_id)
    if chosen.state != OfferState.OFFERED:
        raise TransitionError(f"That offer is {chosen.state} and cannot be declined.")
    chosen.state = OfferState.DECLINED
    return chosen


def cancel(request: Request, actor_id: str) -> Request:
    if actor_id != request.requester_id:
        raise TransitionError("Only the person who asked can cancel this request.")
    _open(request)
    request.cancelled = True
    for live in request.offers:
        if live.state in (OfferState.OFFERED, OfferState.ACCEPTED):
            live.state = OfferState.WITHDRAWN
    return request
