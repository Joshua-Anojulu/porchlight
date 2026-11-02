"""Every illegal transition, asserted to fail.

A protocol is worth what it refuses, so these tests are mostly about refusals.
Each one names the rule it protects.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed import build  # noqa: E402
from server import stages  # noqa: E402
from server.models import OfferState, Reveal, reveal_for  # noqa: E402


@pytest.fixture
def request_and_people():
    people, requests, _ = build()
    return requests["r00"], people


def test_a_requester_cannot_offer_on_their_own_request(request_and_people):
    request, _ = request_and_people
    with pytest.raises(stages.TransitionError, match="your own request"):
        stages.offer(request, request.requester_id, "o1")


def test_a_helper_cannot_offer_twice(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    with pytest.raises(stages.TransitionError, match="already offered"):
        stages.offer(request, "p05", "o2")


def test_only_the_requester_can_accept(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    for impostor in ["p05", "p06", "p29"]:
        with pytest.raises(stages.TransitionError, match="Only the person who asked"):
            stages.accept(request, "o1", impostor)
    assert reveal_for(request, "p05") is Reveal.PUBLIC, "a failed accept must not unlock"


def test_a_helper_cannot_accept_their_own_offer(request_and_people):
    """The attack this protocol exists to stop: a stranger unlocking an address."""
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    with pytest.raises(stages.TransitionError):
        stages.accept(request, "o1", "p05")
    assert reveal_for(request, "p05") is Reveal.PUBLIC


def test_only_one_offer_can_be_accepted(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    stages.offer(request, "p06", "o2")
    stages.accept(request, "o1", request.requester_id)
    with pytest.raises(stages.TransitionError, match="already accepted"):
        stages.accept(request, "o2", request.requester_id)
    assert reveal_for(request, "p06") is Reveal.PUBLIC


def test_accepting_declines_the_others(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    stages.offer(request, "p06", "o2")
    stages.accept(request, "o1", request.requester_id)
    assert [o.state for o in request.offers] == [OfferState.ACCEPTED, OfferState.DECLINED]


def test_nobody_can_offer_after_someone_is_accepted(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    stages.accept(request, "o1", request.requester_id)
    with pytest.raises(stages.TransitionError, match="already been accepted"):
        stages.offer(request, "p07", "o3")


def test_a_declined_or_withdrawn_offer_cannot_be_accepted(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    stages.offer(request, "p06", "o2")
    stages.decline(request, "o1", request.requester_id)
    stages.withdraw(request, "o2", "p06")
    for offer_id in ["o1", "o2"]:
        with pytest.raises(stages.TransitionError, match="cannot be accepted"):
            stages.accept(request, offer_id, request.requester_id)


def test_only_the_helper_can_withdraw_their_offer(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    for impostor in [request.requester_id, "p06"]:
        with pytest.raises(stages.TransitionError, match="Only the helper"):
            stages.withdraw(request, "o1", impostor)


def test_only_the_requester_can_decline_or_cancel(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    with pytest.raises(stages.TransitionError, match="Only the person who asked"):
        stages.decline(request, "o1", "p05")
    with pytest.raises(stages.TransitionError, match="Only the person who asked"):
        stages.cancel(request, "p05")


def test_nothing_happens_on_a_cancelled_request(request_and_people):
    request, _ = request_and_people
    stages.cancel(request, request.requester_id)
    with pytest.raises(stages.TransitionError, match="cancelled"):
        stages.offer(request, "p05", "o1")
    with pytest.raises(stages.TransitionError, match="cancelled"):
        stages.cancel(request, request.requester_id)


def test_an_unknown_offer_id_is_refused(request_and_people):
    request, _ = request_and_people
    with pytest.raises(stages.TransitionError, match="No such offer"):
        stages.accept(request, "nope", request.requester_id)


def test_withdrawing_twice_is_refused(request_and_people):
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    stages.withdraw(request, "o1", "p05")
    with pytest.raises(stages.TransitionError, match="already withdrawn"):
        stages.withdraw(request, "o1", "p05")


def test_a_withdrawn_offer_lets_the_helper_offer_again(request_and_people):
    """Withdrawing is not a punishment; plans change."""
    request, _ = request_and_people
    stages.offer(request, "p05", "o1")
    stages.withdraw(request, "o1", "p05")
    stages.offer(request, "p05", "o2")
    assert request.offers[-1].state == OfferState.OFFERED


def test_reveal_levels_follow_state_not_history(request_and_people):
    request, _ = request_and_people
    assert reveal_for(request, None) is Reveal.PUBLIC
    assert reveal_for(request, request.requester_id) is Reveal.ACCEPTED
    stages.offer(request, "p05", "o1")
    assert reveal_for(request, "p05") is Reveal.PUBLIC
    stages.accept(request, "o1", request.requester_id)
    assert reveal_for(request, "p05") is Reveal.ACCEPTED
    stages.withdraw(request, "o1", "p05")
    assert reveal_for(request, "p05") is Reveal.PUBLIC, "state alone decides, so nothing lingers"
