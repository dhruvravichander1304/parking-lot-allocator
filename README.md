# Parking Lot Allocator

An operating systems project on memory management. Cars are processes and parking slots are memory blocks. The app compares ways of placing cars (contiguous allocation), shows what happens when cars leave, and simulates page replacement (paging).

## Run it

You need Python 3.9 or newer.

```
cd parking-allocator
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in a browser. If `python` doesn't work on your machine, try `python3` (Mac and Linux) or `py` (Windows).

To run the tests (54 tests):

```
python -m unittest -v
```

## The three views

**Parking lot.** Slots are fixed memory blocks, and cars arrive in order. Four strategies are run on the same lot:

- First Fit: take the first slot that is big enough.
- Best Fit: take the smallest slot that is big enough.
- Worst Fit: take the largest slot that is big enough.
- Next Fit: like First Fit, but the search resumes where the last car was parked.

With fixed slots, a slot holds one car, and any unused space is lost (internal fragmentation). Tick **Let a slot hold several cars** to use dynamic slots, where the leftover stays usable.

**Cars leave.** Cars arrive and leave over time in one strip of memory. Free space is kept as holes. When a car leaves, its space merges with any free space next to it. Tick **Compact memory** to slide cars down when a car does not fit but the free space adds up to enough. The page shows the memory after every step.

A script is a comma-separated list. A positive number is a car arriving with that size. A negative number is a car leaving: `-2` means car 2 leaves. Cars are numbered in the order they arrive.

**Paging.** A reference string is a list of page numbers. The page simulates FIFO, LRU and Optimal page replacement with the number of frames you choose, and shows the frame contents after every reference. It also shows:

- Belady's anomaly, a table of faults for each number of frames.
- The working set for a window of references, and where it is bigger than the frames (the sign of thrashing).
- The effective memory access time with a TLB.

## Car lane (blocking and deadlock)

Cars sit in one row with a gate at each end. Write each car with `<` (leaves through the left gate) or `>` (leaves through the right gate). A car can only leave when no car stands between it and its gate, so the cars in the way leave first. The app animates each removal and prints the exact layout after each step.

If two cars block each other (for example `B>, A<`, where B needs A out of the way and A needs B out of the way), that is a deadlock: the app reports the cycle and moves nothing.

## Files

| File | What it does |
| --- | --- |
| `allocator.py` | The four contiguous strategies (fixed and dynamic slots) and their metrics. |
| `timeline.py` | Cars arriving and leaving: holes, merging, compaction, and the script parser. |
| `paging.py` | FIFO, LRU and Optimal replacement, Belady check, working set, TLB access time. |
| `lane.py` | Cars in a lane: blocking order, deadlock detection, exact layout. |
| `app.py` | Flask server: checks input, calls the modules, serves the page. |
| `static/index.html`, `static/style.css`, `static/app.js` | The page and the code that draws the three views. |
| `test_allocator.py`, `test_timeline.py`, `test_paging.py` | Unit tests for the modules and the API. |
| `requirements.txt` | Just Flask. |

## API

| Route | Method | What it returns |
| --- | --- | --- |
| `/api/simulate` | POST | Results for all four strategies on a fixed lot. Body: `{"slots": [...], "cars": [...], "split": false}` |
| `/api/timeline` | POST | Cars arriving and leaving, for all four strategies. Body: `{"memory": 1000, "script": "300, 250, -1", "compact": false}` |
| `/api/paging` | POST | FIFO, LRU and Optimal for a reference string, with the Belady table, working set and TLB time. Body: `{"refs": "7, 0, 1", "frames": 3, "window": 4, "tlb_hit": 80, "tlb_ns": 20, "mem_ns": 100}` |
| `/api/sample` | GET | The textbook lot. |
| `/api/random` | GET | A random lot. Optional `?slots=6&cars=8&seed=1`. |

Bad input gets a 400 response with a short message in `error`.

## Checks you can do by hand

Textbook lot, slots 100, 500, 200, 300, 600 and cars 212, 417, 112, 426, with fixed slots:

| Strategy | Cars parked | Car 426 |
| --- | --- | --- |
| First Fit | 3 of 4 | turned away |
| Best Fit | 4 of 4 | slot 5 |
| Worst Fit | 3 of 4 | turned away |
| Next Fit | 3 of 4 | turned away |

Reference string 7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1 with 3 frames:

| Algorithm | Page faults |
| --- | --- |
| FIFO | 15 |
| LRU | 12 |
| Optimal | 9 |
