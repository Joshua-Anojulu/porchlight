# Porchlight

Porchlight is a prototype of a protocol: ask a neighbour for help without publishing where you live.

## The problem

Mutual aid runs on neighbourhood apps and Facebook groups, which means asking for help requires publishing two things at once. "I am 78, I live alone on Oak Street, and I cannot get to the pharmacy this week" is a request for help and a targeting profile in the same sentence.

The people who most need neighbourhood support are the people for whom that disclosure is least safe. So they do not post, and the network fails exactly where it was supposed to work.

Every board solves discovery. None of them solve disclosure. Porchlight is a board with an access-control protocol underneath, and the protocol is the idea.

## The protocol

Three stages. Information is released only as mutual commitment increases.

| Stage | Who sees what |
| --- | --- |
| **0, public** | Category, a coarse area, a time window. No name, no street, no circumstances. |
| **1, offer** | A neighbour offers. The **requester** now sees the helper's profile, how they are vouched for, and their history. The **helper learns nothing new.** |
| **2, accept** | The requester accepts. Exact address and contact details unlock, for that one helper, for that one request. Contact becomes mutual. |

The asymmetry at stage 1 is deliberate: the person with less power gets information first, and can walk away having revealed nothing.

Either side can withdraw before stage 2 with nothing disclosed. Withdrawing *after* acceptance re-locks the address, because the reveal level is computed from current state rather than stamped onto a record.

## The claim, and the evidence for it

The claim is that an exact address cannot reach a helper before the requester accepts them.

That claim is not enforced by the interface and not enforced by remembering to check. One function builds every payload, and it does so by copying an explicit list of field names for the reveal level it computed. A field that is not on the list has no path into the response. Adding a field to the model does not expose it.

`tests/test_leaks.py` is the file to open first. It serialises every request for every viewer at every stage, walks the whole payload including nested structures, and asserts that no private value appears anywhere in it:

```
for every request
  for every stage in (public, offered, accepted)
    for every viewer in (nobody, a stranger, another helper, the helper, the requester)
      assert no private value appears in the payload, except what that viewer has unlocked
```

36 tests pass. `tests/test_stages.py` asserts the failure of every illegal transition rather than the success of the legal ones, because a protocol is worth what it refuses: a helper cannot accept their own offer, a stranger cannot accept on someone's behalf, a second offer cannot be accepted after the first, a declined offer cannot be revived, and nothing at all happens on a cancelled request.

**The leak test already earned its place.** Writing it surfaced an under-specified rule: once an offer is accepted, the requester sees the helper's phone number. That is correct behaviour, mutual contact between two people who have agreed to meet, but it was never written down anywhere. It is now a named rule with a test of its own.

## What the demo shows

The interface has a panel marked "Show the exact response the server sent". It prints the raw payload for the selected request, as the signed-in person received it, with private values highlighted. Watch the `address` field: at stage 0 and stage 1 it is not dimmed, not masked, and not `null`. It is absent. At stage 2 it appears.

That is the thirty seconds worth having in a video, because it demonstrates the claim instead of asserting it.

Walkthrough: open as "Nobody", pick the pharmacy request, note there is no address field. Sign in as Ruth Delacroix, offer to help, and see that the response did not change. Sign in as Maria Alvarez, who posted it, and see Ruth's profile with "Vouched for by Jonah Berg". Accept. Sign back in as Ruth: the address is there now. Sign in as anyone else: it is not.

## Trust without ratings

There are no stars and no score. A rating system scores people on how they behave, and in mutual aid the people being scored most are the people asking for help; someone who needs help often would accumulate a bad score for needing it.

Instead there is a vouch graph: directed, positive-only claims from real prior interaction. Trust between two people is the best path through it, decayed by length, `T = 0.6 ** hops`, capped at three hops. A neighbour you vouched for reads 0.6, a friend of theirs 0.36, and anyone further is a stranger.

Two deliberate choices:

- **The number is never shown.** "Vouched for by Jonah Berg" is something a person can act on. "Trust 0.36" is not.
- **The path is never shown past the first hop.** A path names third parties and discloses who vouched for whom to someone party to neither. So the renderer names only people the viewer vouched for directly; anything beyond is summarised as "connected through 2 neighbours you trust".

A stranger is described without blame: "They are a stranger to your part of the network. That is not a mark against them; it means this connection carries no information."

## The coarse area

The public board shows a geohash prefix. A geohash interleaves latitude and longitude bits into base 32, so truncating it discards the low-order bits of both coordinates: the prefix names a rectangle, and every address inside shares it. Six characters is roughly 1.0 km by 0.6 km at this latitude.

The pin is plotted at the **cell centre**, never the real point, so the map carries exactly the information the prefix already carries and no more. `test_neighbours_in_the_same_cell_are_indistinguishable` holds the mechanism in place, and the encoder is checked against the published reference values (`u4pruydqqvj`, `ezs42`).

## Run it

Needs Python 3.11 or newer.

```bash
pip install -r requirements.txt
pytest -q                                    # 36 tests
uvicorn server.api:app --port 8000           # then open http://127.0.0.1:8000
```

State is in memory and reseeds on restart; "Reset demo" does the same thing without one.

```
server/models.py   the model, the reveal levels, and the field allowlists
server/stages.py   the state machine, every transition guarded
server/geo.py      geohash encoding and the coarse cell
server/trust.py    bounded BFS over the vouch graph, rendered in words
server/api.py      the endpoints
web/index.html     one page, no build step, with the raw-payload panel
seed.py            30 invented people, a hand-built vouch graph, four requests
tests/             the leak property test, the refusals, trust and geo
```

## What this is not

This is a prototype of a protocol, not a service anyone should launch.

- **There is no authentication.** Signing in is a person id in a query parameter. That is not security and does not pretend to be; the project is about what a protocol discloses, and a login would add no evidence for that claim. A real deployment needs real accounts before anything else here matters.
- **No identity verification, no abuse reporting, no safeguarding policy.** Staged disclosure reduces what a bad actor learns before commitment. It does nothing about a bad actor the requester accepts. That is a different and harder problem, and a real service needs an answer to it.
- **A coarse cell is not anonymity.** Someone who watches the board over weeks can link repeated requests from the same cell and category to one household. Per-request jitter would break the "is it near me" question the board exists to answer, so this version does not attempt it and states the limitation instead.
- **The vouch graph is seeded, not earned.** In a real deployment, how a first vouch comes into existence is the hard part, and it is not solved here.
- **In-memory storage.** Restarting loses everything. Fine for a prototype, wrong for anything else.

Naming these is not a weakness in the submission. The parts that are built are built properly and tested; the parts that are not built are stated rather than implied.

## AI disclosure

- **Joshua Anojulu**: project lead. Chose the problem and the event, and directs the build.
- **Claude (Anthropic)**: wrote the protocol design, `server/`, `web/`, `seed.py`, the tests and this README. The choices to make disclosure a field allowlist rather than a UI concern, to name only first-hop connectors in the trust rendering, and to plot the cell centre rather than the point were made while writing the code and are explained above.

Earlier project specification and architecture planning: Claude.

All people, addresses and phone numbers in the seed data are invented. No real person's data appears anywhere in this repository.
