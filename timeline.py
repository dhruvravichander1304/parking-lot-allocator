"""
Cars that arrive AND leave: dynamic partitioning over time.

The lot is one strip of memory from address 0 to MEMORY. Free space is kept as
a list of holes. Each arrival picks one hole with the same rule as before
(first, best, worst or next fit). When a car leaves, its space becomes a hole
again and merges with any hole touching it (coalescing). If a car is turned
away while the free space adds up to enough, the optional compaction slides
every parked car down to address 0, so all the free space becomes one hole.

Script format (used by the page and the API):
    212     a car of size 212 arrives. Cars are numbered in arrival order: 1, 2, 3...
    -2      car 2 leaves
"""

import re

from allocator import STRATEGIES, STRATEGY_NAMES

MAX_MEMORY = 10_000
MAX_SIZE = 10_000
MAX_STEPS = 40

REASON = {
    "first": "It is the first hole that fits.",
    "best": "It is the smallest hole that fits.",
    "worst": "It is the largest hole that fits.",
    "next": "It is the next hole that fits after the last car.",
}


def parse_script(text):
    """Turn '212, 417, -1, 112' into a list of events. Raises ValueError with a readable message."""
    tokens = [t for t in re.split(r"[\s,]+", (text or "").strip()) if t]
    if not tokens:
        raise ValueError("Give at least one step, for example 212, 417, -1.")
    if len(tokens) > MAX_STEPS:
        raise ValueError(f"A script can have at most {MAX_STEPS} steps.")

    events = []
    arrivals = 0
    for tok in tokens:
        try:
            n = int(tok)
        except ValueError:
            raise ValueError(f"'{tok}' is not a whole number.")
        if n == 0:
            raise ValueError("Use a size like 212 for a car arriving, or -2 for car 2 leaving.")
        if n > 0:
            if n > MAX_SIZE:
                raise ValueError(f"Car sizes must be at most {MAX_SIZE}.")
            events.append({"op": "arrive", "size": n, "car": arrivals})
            arrivals += 1
        else:
            k = -n
            if k > arrivals:
                raise ValueError(f"Car {k} has not arrived yet, so it cannot leave.")
            events.append({"op": "leave", "car": k - 1})
    return events


def _choose_hole(strategy, holes, need, rover):
    """holes are kept sorted by address, so list order is address order."""
    fitting = [i for i, h in enumerate(holes) if h["size"] >= need]
    if not fitting:
        return None
    if strategy == "first":
        return fitting[0]
    if strategy == "best":
        return min(fitting, key=lambda i: (holes[i]["size"], holes[i]["start"]))
    if strategy == "worst":
        return min(fitting, key=lambda i: (-holes[i]["size"], holes[i]["start"]))
    if strategy == "next":
        ahead = [i for i in fitting if holes[i]["start"] >= rover]
        return (ahead or fitting)[0]
    raise ValueError(f"unknown strategy: {strategy}")


def _release(holes, block):
    """Return a block's space to the holes and merge touching holes. Returns how many holes it joined."""
    start, end = block["start"], block["start"] + block["size"]
    left = next((h for h in holes if h["start"] + h["size"] == start), None)
    right = next((h for h in holes if h["start"] == end), None)
    joined = 0
    new_start, new_end = start, end
    for h in (left, right):
        if h is not None:
            holes.remove(h)
            joined += 1
            new_start = min(new_start, h["start"])
            new_end = max(new_end, h["start"] + h["size"])
    holes.append({"start": new_start, "size": new_end - new_start})
    holes.sort(key=lambda h: h["start"])
    return joined


def _compact(parked, memory, holes):
    """Slide every parked car down to address 0. Returns how many cars moved."""
    moved = 0
    addr = 0
    for b in parked:  # parked is kept in address order
        if b["start"] != addr:
            b["start"] = addr
            moved += 1
        addr += b["size"]
    holes[:] = [{"start": addr, "size": memory - addr}] if addr < memory else []
    return moved


def _total_free(holes):
    return sum(h["size"] for h in holes)


def _snapshot(parked, holes):
    return {"blocks": [dict(b) for b in parked], "holes": [dict(h) for h in holes]}


def run_timeline(strategy, memory, events, compact=False):
    """Play the events in order with one strategy. Returns the steps, a memory snapshot after each, and metrics."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if not 1 <= memory <= MAX_MEMORY:
        raise ValueError(f"Memory must be between 1 and {MAX_MEMORY}.")

    holes = [{"start": 0, "size": memory}]
    parked = []          # cars in memory, in address order
    steps = []
    rover = 0
    peak_holes = 1
    c = {"parked": 0, "turned_away": 0, "external": 0, "compactions": 0, "moves": 0, "left": 0}

    for ev in events:
        if ev["op"] == "arrive":
            car, need = ev["car"], ev["size"]
            notes = []
            idx = _choose_hole(strategy, holes, need, rover)

            if idx is None and compact and _total_free(holes) >= need:
                moved = _compact(parked, memory, holes)
                c["compactions"] += 1
                c["moves"] += moved
                notes.append(f"Memory is compacted first: {moved} car(s) slide down to close the gaps.")
                idx = _choose_hole(strategy, holes, need, rover)

            if idx is None:
                c["turned_away"] += 1
                free_total = _total_free(holes)
                if free_total >= need:
                    c["external"] += 1
                    why = (f"{free_total} units are free, but no single hole is {need} or bigger. "
                           f"That is external fragmentation.")
                else:
                    why = f"only {free_total} units are free."
                text = " ".join(notes + [f"Car {car + 1} (size {need}) is turned away: {why}"])
                placed = False
            else:
                hole = holes[idx]
                before, start = hole["size"], hole["start"]
                hole["start"] += need
                hole["size"] -= need
                if hole["size"] == 0:
                    del holes[idx]
                parked.append({"car": car, "start": start, "size": need})
                parked.sort(key=lambda b: b["start"])
                rover = start + need
                c["parked"] += 1
                text = " ".join(notes + [
                    f"Car {car + 1} (size {need}) parks at address {start}, in a hole of {before}. "
                    f"{REASON[strategy]}"
                ])
                placed = True
        else:
            car = ev["car"]
            block = next((b for b in parked if b["car"] == car), None)
            if block is None:
                text = f"Car {car + 1} is not parked, so there is nothing to free."
                placed = None
            else:
                parked.remove(block)
                joined = _release(holes, block)
                c["left"] += 1
                text = f"Car {car + 1} leaves and frees {block['size']} units at address {block['start']}."
                if joined == 2:
                    text += " It joins the free space on both sides into one hole."
                elif joined == 1:
                    text += " It joins the free space next to it."
                placed = None

        peak_holes = max(peak_holes, len(holes))
        steps.append({
            "op": ev["op"],
            "car": car,
            "size": ev.get("size"),
            "placed": placed,
            "text": text,
            "memory": _snapshot(parked, holes),
        })

    used = sum(b["size"] for b in parked)
    largest = max((h["size"] for h in holes), default=0)
    return {
        "strategy": strategy,
        "name": STRATEGY_NAMES[strategy],
        "memory": memory,
        "steps": steps,
        "metrics": {
            "parked": c["parked"],
            "turned_away": c["turned_away"],
            "external_rejections": c["external"],
            "compactions": c["compactions"],
            "cars_moved": c["moves"],
            "cars_left": c["left"],
            "in_memory": len(parked),
            "used": used,
            "utilization": round(100 * used / memory, 1),
            "free_now": _total_free(holes),
            "holes_now": len(holes),
            "largest_hole_now": largest,
            "peak_holes": peak_holes,
        },
    }


def compare_timeline(memory, events, compact=False):
    """Run all four strategies on the same script and name the winners (most cars parked, then fewest turned away)."""
    results = {s: run_timeline(s, memory, events, compact) for s in STRATEGIES}
    best = max(
        (results[s]["metrics"]["parked"], -results[s]["metrics"]["turned_away"]) for s in STRATEGIES
    )
    winners = [
        s for s in STRATEGIES
        if (results[s]["metrics"]["parked"], -results[s]["metrics"]["turned_away"]) == best
    ]
    return {"results": results, "winners": winners, "compact": compact, "events": events}
