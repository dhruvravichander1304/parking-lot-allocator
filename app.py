import re
"""
Flask backend for the Parking Lot Allocator.

    python app.py        then open http://127.0.0.1:5000
"""
import random

from flask import Flask, jsonify, request, send_from_directory

from allocator import compare
from paging import analyse, parse_refs, MAX_FRAMES
from timeline import MAX_MEMORY, compare_timeline, parse_script
from lane import move_out, parse_lane

app = Flask(__name__, static_folder="static", static_url_path="/static")

MAX_ITEMS = 30
MAX_SIZE = 10_000


def _clean_sizes(raw, label):
    """Turn the incoming list into positive ints, or raise ValueError with a readable message."""
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Give at least one value for {label}.")
    if len(raw) > MAX_ITEMS:
        raise ValueError(f"{label} can have at most {MAX_ITEMS} values.")
    out = []
    for v in raw:
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise ValueError(f"'{v}' in {label} is not a whole number.")
        if n <= 0 or n > MAX_SIZE:
            raise ValueError(f"Each value in {label} must be between 1 and {MAX_SIZE}.")
        out.append(n)
    return out


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/simulate")
def api_simulate():
    data = request.get_json(silent=True) or {}
    try:
        slots = _clean_sizes(data.get("slots"), "slots")
        cars = _clean_sizes(data.get("cars"), "cars")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    split = bool(data.get("split", False))
    return jsonify({"slots": slots, "cars": cars, **compare(slots, cars, split)})


@app.post("/api/timeline")
def api_timeline():
    """Cars arrive and leave. Body: {"memory": 1000, "script": "300, 200, -1, 150", "compact": false}"""
    data = request.get_json(silent=True) or {}
    try:
        memory = _whole(data.get("memory", 1000), "Memory size")
        if not 1 <= memory <= MAX_MEMORY:
            raise ValueError(f"Memory must be between 1 and {MAX_MEMORY}.")
        events = parse_script(data.get("script", ""))
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"memory": memory, **compare_timeline(memory, events, bool(data.get("compact", False)))})


def _whole(value, label):
    """Read a whole number from a form or JSON value, with a readable message if it is not one."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")


@app.post("/api/lane")
def api_lane():
    """Cars in a lane with a gate at each end. Body: {"lane": "C<, A<", "requests": "A"}"""
    data = request.get_json(silent=True) or {}
    try:
        cars = parse_lane(data.get("lane", ""))
        requests = [r for r in re.split(r"[\s,]+", str(data.get("requests", "")).strip()) if r]
        if not requests:
            raise ValueError("Say which car should move out, for example A.")
        return jsonify(move_out(cars, requests))
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/paging")
def api_paging():
    """Page replacement. Body: {"refs": "7, 0, 1", "frames": 3, "window": 4, "tlb_hit": 80, "tlb_ns": 20, "mem_ns": 100}"""
    data = request.get_json(silent=True) or {}
    try:
        refs = parse_refs(data.get("refs", ""))
        frames = _whole(data.get("frames", 3), "Frames")
        if not 1 <= frames <= MAX_FRAMES:
            raise ValueError(f"Frames must be between 1 and {MAX_FRAMES}.")
        window = data.get("window")
        window = None if window in (None, "") else _whole(window, "The working-set window")
        if window is not None and window < 1:
            raise ValueError("The working-set window must be at least 1.")
        tlb = [data.get("tlb_hit"), data.get("tlb_ns"), data.get("mem_ns")]
        if all(v in (None, "") for v in tlb):
            tlb_hit, tlb_ns, mem_ns = None, None, None
        else:
            try:
                tlb_hit, tlb_ns, mem_ns = float(tlb[0]), float(tlb[1]), float(tlb[2])
            except (TypeError, ValueError):
                raise ValueError("The TLB hit ratio and both times must be numbers.")
            if not 0 <= tlb_hit <= 100 or tlb_ns < 0 or mem_ns < 0:
                raise ValueError("TLB hit must be 0 to 100 percent, and times cannot be negative.")
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(analyse(refs, frames, window, tlb_hit, tlb_ns, mem_ns))


@app.get("/api/random")
def api_random():
    """A random lot for quick experiments. Optional ?slots=6&cars=8&seed=1"""
    try:
        n_slots = max(2, min(12, int(request.args.get("slots", 6))))
        n_cars = max(2, min(15, int(request.args.get("cars", 8))))
    except ValueError:
        return jsonify({"error": "slots and cars must be whole numbers."}), 400
    seed = request.args.get("seed")
    rng = random.Random(int(seed)) if seed and seed.lstrip("-").isdigit() else random.Random()
    return jsonify({
        "slots": [rng.randrange(10, 71, 5) * 10 for _ in range(n_slots)],
        "cars": [rng.randrange(40, 521, 10) for _ in range(n_cars)],
    })


@app.get("/api/sample")
def api_sample():
    """The classic textbook example, where the three strategies disagree."""
    return jsonify({"slots": [100, 500, 200, 300, 600], "cars": [212, 417, 112, 426]})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
