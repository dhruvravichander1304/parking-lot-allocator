"""
Memory allocation strategies, dressed up as a parking lot.

    car          -> process (its size is the memory it needs)
    parking slot -> memory block / hole
    parking a car -> allocating a process

Four strategies are compared:
    first : take the first slot that is big enough
    best  : take the smallest slot that is big enough
    worst : take the largest slot that is big enough
    next  : like first fit, but the search resumes where the last car was parked

Two lot styles are supported:
    split=False  fixed partitions. A slot holds at most one car, and whatever
                 space the car doesn't use is lost (internal fragmentation).
    split=True   dynamic partitions. A slot can hold several cars until it runs
                 out of room, so the leftover stays usable.
"""

STRATEGIES = ("first", "best", "worst", "next")

STRATEGY_NAMES = {
    "first": "First Fit",
    "best": "Best Fit",
    "worst": "Worst Fit",
    "next": "Next Fit",
}


def _pick(strategy, candidates, rover=0):
    """candidates is a list of (index, free_space) that can hold the car.

    rover is the slot where the previous car was parked (used by next fit only).
    """
    if not candidates:
        return None
    if strategy == "first":
        return candidates[0][0]
    if strategy == "next":
        # resume the search at the rover; wrap to the start if nothing fits after it
        ahead = [c for c in candidates if c[0] >= rover]
        return (ahead or candidates)[0][0]
    if strategy == "best":
        # smallest free space, earliest slot wins a tie
        return min(candidates, key=lambda c: (c[1], c[0]))[0]
    if strategy == "worst":
        # largest free space, earliest slot wins a tie
        return min(candidates, key=lambda c: (-c[1], c[0]))[0]
    raise ValueError(f"unknown strategy: {strategy}")


def simulate(strategy, slot_sizes, car_sizes, split=False):
    """Run one strategy and return a dict with the final lot, a step log and metrics."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")

    slots = [
        {"id": i, "size": s, "free": s, "cars": [], "closed": False}
        for i, s in enumerate(slot_sizes)
    ]
    steps = []
    rejected = []
    rover = 0

    for car_id, car_size in enumerate(car_sizes):
        candidates = [
            (s["id"], s["free"])
            for s in slots
            if not s["closed"] and s["free"] >= car_size
        ]
        chosen = _pick(strategy, candidates, rover)

        if chosen is None:
            rejected.append({"car": car_id, "size": car_size})
            steps.append({
                "car": car_id,
                "size": car_size,
                "slot": None,
                "fits": [],
                "text": f"Car {car_id + 1} (size {car_size}) found no slot big enough, so it is turned away.",
            })
            continue

        slot = slots[chosen]
        rover = chosen
        before = slot["free"]
        slot["cars"].append({"car": car_id, "size": car_size})
        slot["free"] -= car_size
        if not split:
            slot["closed"] = True  # fixed partition: one car per slot

        fits = [c[0] for c in candidates]
        reason = {
            "first": "it is the first slot that fits",
            "best": "it leaves the least space over",
            "worst": "it leaves the most space over",
            "next": "it is the next slot that fits after the last car",
        }[strategy]
        steps.append({
            "car": car_id,
            "size": car_size,
            "slot": chosen,
            "fits": fits,
            "leftover": before - car_size,
            "text": (
                f"Car {car_id + 1} (size {car_size}) goes to slot {chosen + 1} "
                f"(free {before}) because {reason}. Leftover: {before - car_size}."
            ),
        })

    capacity = sum(slot_sizes)
    used = sum(c["size"] for s in slots for c in s["cars"])
    parked = len(car_sizes) - len(rejected)

    internal = 0   # space lost inside a slot that is closed to new cars
    external = 0   # space still free in slots that are open but went unused
    for s in slots:
        if s["closed"]:
            internal += s["free"]
        else:
            external += s["free"]

    smallest_rejected = min((r["size"] for r in rejected), default=None)

    return {
        "strategy": strategy,
        "name": STRATEGY_NAMES[strategy],
        "slots": slots,
        "steps": steps,
        "rejected": rejected,
        "metrics": {
            "parked": parked,
            "rejected": len(rejected),
            "capacity": capacity,
            "used": used,
            "utilization": round(100 * used / capacity, 1) if capacity else 0.0,
            "wasted": capacity - used,
            "internal_fragmentation": internal,
            "free_space": external,
            # free space exists in total but no single slot can take the smallest rejected car
            "external_fragmentation": external if rejected and external >= (smallest_rejected or 0) else 0,
        },
    }


def compare(slot_sizes, car_sizes, split=False):
    """Run all three strategies on the same lot and name the winner."""
    results = {s: simulate(s, slot_sizes, car_sizes, split) for s in STRATEGIES}

    # most cars parked wins; fewer wasted units breaks the tie
    ranked = sorted(
        STRATEGIES,
        key=lambda s: (-results[s]["metrics"]["parked"], results[s]["metrics"]["wasted"]),
    )
    best_key = (
        results[ranked[0]]["metrics"]["parked"],
        results[ranked[0]]["metrics"]["wasted"],
    )
    winners = [
        s for s in STRATEGIES
        if (results[s]["metrics"]["parked"], results[s]["metrics"]["wasted"]) == best_key
    ]
    return {"results": results, "winners": winners, "split": split}
