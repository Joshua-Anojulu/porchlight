"""A fictional neighbourhood: 30 invented people, a vouch graph, and four requests.

Every person, address and phone number here is made up. The coordinates are
scattered around a point in Prosper, Texas so the coarse cells are realistic;
no real address is used.
"""
from __future__ import annotations

import random

from server.models import Person, Request, Vouch

SEED = 20261130
CENTRE = (33.2360, -96.8010)

NAMES = [
    "Maria Alvarez", "Desmond Clark", "Priya Raman", "Tom Whitfield", "Ada Nwosu",
    "Jonah Berg", "Leila Haddad", "Grace Okonkwo", "Sam Petrov", "Ruth Delacroix",
    "Noor Rahimi", "Felix Mbeki", "Hana Sato", "Ivan Kovacs", "Rosa Linde",
    "Omar Farouk", "Bea Lindqvist", "Caleb Monroe", "Yuki Tanaka", "Nadia Sorokin",
    "Elias Vargas", "Marta Kowal", "Theo Ashworth", "Imani Boateng", "Juno Park",
    "Rafael Costa", "Edith Barlow", "Kwame Asante", "Lucia Ferraro", "Ben Oyelaran",
]

STREETS = ["Coleman St", "Preston Rd", "First St", "Craig Rd", "La Cima Blvd",
           "Broadway St", "Church St", "Gorgeous Dr", "Pasewark Dr", "Shawnee Trl"]

# Who vouches for whom, by index. Directed and positive only. Hand-built so the
# demo has a two-hop path and a stranger, rather than a random graph that might
# have neither.
VOUCHES = [
    (0, 1, "Watched her dog for a week"), (0, 2, "Neighbours for six years"),
    (0, 5, "Same block committee"), (1, 3, "Drove him to the clinic"),
    (1, 6, "Shared a fence repair"), (2, 7, "Met through the school run"),
    (2, 3, "Lent him a ladder"), (3, 8, "Helped move a sofa"),
    (5, 9, "Volunteered together"), (6, 10, "Known since 2019"),
    (7, 11, "Shared a ride to work"), (8, 12, "Fixed her car"),
    (9, 13, "Church group"), (4, 0, "She brought meals after surgery"),
    (4, 14, "Book club"), (14, 15, "Coached the same team"),
    (10, 16, "Allotment neighbours"), (11, 17, "Night shift together"),
    (12, 18, "Taught his kids"), (13, 19, "Walked her mother's dog"),
    (16, 20, "Built a shed together"), (17, 21, "Shared childcare"),
    (18, 22, "Old colleagues"), (19, 23, "Choir"), (20, 24, "Repaired a roof"),
    (21, 25, "Weekly chess"), (22, 26, "Gardening club"), (23, 27, "Cycling group"),
    (24, 28, "Neighbourhood watch"), (25, 29, "Language exchange"),
    (1, 2, "Borrowed each other's tools"), (3, 1, "Returned the favour"),
]

REQUESTS = [
    dict(requester=0, category="Pharmacy pickup", window="Any afternoon this week",
         details="Two prescriptions waiting under my name. I cannot drive at the moment.",
         created="2026-11-24"),
    dict(requester=4, category="Help with heavy shopping", window="Saturday morning",
         details="One large shop, mostly tins and a bag of soil. Lift is out of order.",
         created="2026-11-25"),
    dict(requester=12, category="Lift to an appointment", window="Thursday, 9am to 11am",
         details="Appointment at 9:40, about fifteen minutes away. Return trip too if possible.",
         created="2026-11-26"),
    dict(requester=19, category="Dog walk", window="Weekday evenings",
         details="Small dog, twenty minutes, very easy. I am recovering from a sprain.",
         created="2026-11-27"),
]


def build() -> tuple[dict[str, Person], dict[str, Request], list[Vouch]]:
    rng = random.Random(SEED)
    people: dict[str, Person] = {}
    addresses: dict[str, str] = {}
    points: dict[str, tuple[float, float]] = {}
    for index, name in enumerate(NAMES):
        person_id = f"p{index:02d}"
        people[person_id] = Person(
            id=person_id,
            display_name=name,
            phone=f"555-0{rng.randrange(100, 999)}",
            joined=f"20{rng.randrange(21, 26)}",
            helped_count=rng.randrange(0, 14),
        )
        addresses[person_id] = f"{rng.randrange(100, 2400)} {rng.choice(STREETS)}"
        points[person_id] = (CENTRE[0] + rng.uniform(-0.035, 0.035),
                             CENTRE[1] + rng.uniform(-0.035, 0.035))

    requests: dict[str, Request] = {}
    for index, spec in enumerate(REQUESTS):
        owner = f"p{spec['requester']:02d}"
        latitude, longitude = points[owner]
        request_id = f"r{index:02d}"
        requests[request_id] = Request(
            id=request_id, requester_id=owner, category=spec["category"],
            window=spec["window"], latitude=latitude, longitude=longitude,
            address=addresses[owner], details=spec["details"], created=spec["created"],
        )

    vouches = [Vouch(f"p{a:02d}", f"p{b:02d}", basis) for a, b, basis in VOUCHES]
    return people, requests, vouches
