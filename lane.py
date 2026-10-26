"""
A one-lane parking strip with a gate at each end.

Cars sit in a row, left to right. Each car has an exit gate: "<" = the left gate,
">" = the right gate. A car can leave only when no car stands between it and its
gate. Cars standing in the way must leave first, nearest first.

Deadlock: if cars block each other in a loop (e.g. B exits right but A stands
between B and the right gate, while A exits left but B stands between A and the
left gate), nobody can move. That is circular wait, one of the four deadlock
conditions. The app detects it and refuses to move anything.

Script format: car names left to right with an exit mark, e.g. "C<, A<".
"""

import re

MAX_CARS = 12


def parse_lane(text):
    tokens = [t for t in re.split(r"[\s,]+", (text or "").strip()) if t]
    if not tokens:
        raise ValueError("Give at least one car, for example C<, A<.")
    if len(tokens) > MAX_CARS:
        raise ValueError(f"The lane holds at most {MAX_CARS} cars.")
    cars, names = [], set()
    for tok in tokens:
        m = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)([<>])", tok)
        if not m:
            raise ValueError(f"'{tok}' is not a car. Write a name then < (left gate) or > (right gate), like A< or B>.")
        name, mark = m.groups()
        if name in names:
            raise ValueError(f"Car {name} is in the lane twice.")
        names.add(name)
        cars.append({"name": name, "exit": "left" if mark == "<" else "right"})
    return cars


def _index(cars, name):
    for i, c in enumerate(cars):
        if c["name"] == name:
            return i
    raise ValueError(f"Car {name} is not in the lane.")


def _blockers(cars, i):
    """Indexes of the cars standing between car i and its exit gate."""
    if cars[i]["exit"] == "left":
        return list(range(0, i))
    return list(range(i + 1, len(cars)))


def wait_for(cars):
    """Who waits for whom: car -> the cars blocking it."""
    return {cars[i]["name"]: [cars[j]["name"] for j in _blockers(cars, i)] for i in range(len(cars))}


def find_deadlock(cars):
    """Return the cycle of cars that block each other, or None. Depth-first search on the wait-for graph."""
    graph = wait_for(cars)
    state = {}
    stack = []

    def visit(n):
        state[n] = 1
        stack.append(n)
        for m in graph[n]:
            if state.get(m, 0) == 1:
                return stack[stack.index(m):] + [m]
            if state.get(m, 0) == 0:
                cycle = visit(m)
                if cycle:
                    return cycle
        stack.pop()
        state[n] = 2
        return None

    for n in graph:
        if state.get(n, 0) == 0:
            cycle = visit(n)
            if cycle:
                return cycle
    return None


def layout(cars):
    """The exact layout: each car with its position, exit gate and what it waits for."""
    graph = wait_for(cars)
    out = []
    for i, c in enumerate(cars):
        out.append({
            "position": i + 1,
            "car": c["name"],
            "exit": c["exit"],
            "waits_for": graph[c["name"]],
        })
    return out


def layout_text(cars):
    """A one-line picture of the lane, for printing on the dashboard."""
    if not cars:
        return "LEFT GATE  [ empty ]  RIGHT GATE"
    parts = [f"{i + 1}:{c['name']}{'<' if c['exit'] == 'left' else '>'}" for i, c in enumerate(cars)]
    return "LEFT GATE  [ " + "  ][ ".join(parts) + " ]  RIGHT GATE"


def _leave(cars, name, target, events):
    """Remove car `name`, first removing any cars in its way (nearest first)."""
    while True:
        i = _index(cars, name)
        blockers = _blockers(cars, i)
        if not blockers:
            break
        nearest = min(blockers, key=lambda j: abs(j - i))
        _leave(cars, cars[nearest]["name"], name, events)
    i = _index(cars, name)
    gone = cars.pop(i)
    if target is None:
        text = f"{gone['name']} leaves through the {gone['exit']} gate."
    else:
        text = f"{gone['name']} is in the way of {target}, so it leaves first through the {gone['exit']} gate."
    events.append({"car": gone["name"], "text": text, "layout": layout(cars), "layout_text": layout_text(cars)})


def move_out(cars, requests):
    """
    Process the requests in order. Each request is a car that wants to leave.
    Returns the steps, the lane before and after, and the deadlock if one stops the process.
    The lane list passed in is not changed.
    """
    lane = [dict(c) for c in cars]
    before = {"layout": layout(lane), "layout_text": layout_text(lane)}
    events = []
    deadlock = None

    for name in requests:
        _index(lane, name)  # raises a readable error if the car is not there
        cycle = find_deadlock(lane)
        if cycle:
            deadlock = {
                "cycle": cycle,
                "text": "Deadlock: " + " -> ".join(cycle) + " each wait for the next, so none can move. "
                        "Nothing was moved.",
                "requested": name,
            }
            events.append({"car": name, "text": deadlock["text"], "layout": layout(lane),
                           "layout_text": layout_text(lane), "deadlock": True})
            break
        _leave(lane, name, None, events)

    return {
        "before": before,
        "steps": events,
        "after": {"layout": layout(lane), "layout_text": layout_text(lane)},
        "deadlock": deadlock,
    }
