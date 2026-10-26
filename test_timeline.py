"""Cars that arrive and leave: merging holes and compaction. Run with: python -m unittest -v"""
import random
import unittest

from app import app
from timeline import compare_timeline, parse_script, run_timeline

STRATEGIES = ("first", "best", "worst", "next")


def holes_of(result, step=-1):
    return [(h["start"], h["size"]) for h in result["steps"][step]["memory"]["holes"]]


class Script(unittest.TestCase):
    def test_parses_arrivals_and_departures(self):
        ev = parse_script("300, 200, -2, 150")
        self.assertEqual(ev, [
            {"op": "arrive", "size": 300, "car": 0},
            {"op": "arrive", "size": 200, "car": 1},
            {"op": "leave", "car": 1},
            {"op": "arrive", "size": 150, "car": 2},
        ])

    def test_rejects_bad_scripts(self):
        for bad in ("", "abc", "0", "-3, 200", "200, -2, -2, 5, -9"):
            with self.assertRaises(ValueError, msg=bad):
                parse_script(bad)


class Coalescing(unittest.TestCase):
    def test_everything_leaves_and_memory_is_one_hole_again(self):
        r = run_timeline("first", 1000, parse_script("200, 200, 200, -1, -2, -3"))
        self.assertEqual(holes_of(r), [(0, 1000)])
        self.assertEqual(r["metrics"]["in_memory"], 0)

    def test_leaving_car_joins_the_hole_next_to_it(self):
        r = run_timeline("first", 1000, parse_script("300, 200, 300, -2, -1"))
        self.assertIn("joins the free space next to it", r["steps"][4]["text"])
        self.assertEqual(holes_of(r), [(0, 500), (800, 200)])

    def test_leaving_car_between_two_holes_merges_all_three(self):
        r = run_timeline("first", 900, parse_script("300, 300, 300, -1, -3, -2"))
        self.assertIn("joins the free space on both sides", r["steps"][5]["text"])
        self.assertEqual(holes_of(r), [(0, 900)])


class Compaction(unittest.TestCase):
    SCRIPT = "200, 200, 200, 200, -1, -3, 300"

    def test_without_compaction_a_car_is_turned_away_by_external_fragmentation(self):
        r = run_timeline("first", 1000, parse_script(self.SCRIPT), compact=False)
        self.assertEqual(r["metrics"]["turned_away"], 1)
        self.assertEqual(r["metrics"]["external_rejections"], 1)
        self.assertIn("external fragmentation", r["steps"][-1]["text"])

    def test_compaction_slides_cars_down_and_the_car_parks(self):
        r = run_timeline("first", 1000, parse_script(self.SCRIPT), compact=True)
        self.assertEqual(r["metrics"]["turned_away"], 0)
        self.assertEqual(r["metrics"]["compactions"], 1)
        self.assertEqual(r["metrics"]["cars_moved"], 2)
        last = r["steps"][-1]
        self.assertEqual(last["memory"]["blocks"][-1]["start"], 400)  # the new car sits after the two cars that moved

    def test_compare_names_all_strategies_when_they_tie(self):
        out = compare_timeline(1000, parse_script(self.SCRIPT), compact=True)
        self.assertEqual(set(out["results"]), set(STRATEGIES))
        self.assertEqual(out["winners"], list(STRATEGIES))


class Invariants(unittest.TestCase):
    def test_memory_always_adds_up_and_holes_never_touch(self):
        rng = random.Random(11)
        for _ in range(120):
            memory = rng.randrange(200, 2000)
            tokens, arrivals = [], 0
            for _ in range(rng.randrange(3, 25)):
                if arrivals and rng.random() < 0.35:
                    tokens.append(str(-rng.randrange(1, arrivals + 1)))
                else:
                    tokens.append(str(rng.randrange(20, 600)))
                    arrivals += 1
            events = parse_script(", ".join(tokens))
            for strategy in STRATEGIES:
                for compact in (False, True):
                    r = run_timeline(strategy, memory, events, compact)
                    for step in r["steps"]:
                        blocks = step["memory"]["blocks"]
                        holes = step["memory"]["holes"]
                        spans = sorted([(b["start"], b["size"]) for b in blocks] + [(h["start"], h["size"]) for h in holes])
                        pos = 0
                        for start, size in spans:  # no gaps, no overlaps
                            self.assertEqual(start, pos)
                            self.assertGreater(size, 0)
                            pos = start + size
                        self.assertEqual(pos, memory)
                        for h1, h2 in zip(holes, holes[1:]):  # neighbouring holes are always merged
                            self.assertLess(h1["start"] + h1["size"], h2["start"])


class Api(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_timeline_ok(self):
        res = self.client.post("/api/timeline", json={"memory": 1000, "script": "200, 200, 200, 200, -1, -3, 300", "compact": True})
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(set(body["results"]), set(STRATEGIES))

    def test_timeline_rejects_bad_input(self):
        for payload in ({"memory": 0, "script": "10"}, {"memory": 100, "script": ""}, {"memory": 100, "script": "10, -4"}):
            res = self.client.post("/api/timeline", json=payload)
            self.assertEqual(res.status_code, 400, payload)
            self.assertIn("error", res.get_json())


if __name__ == "__main__":
    unittest.main()
