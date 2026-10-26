"""
Paging: which page to throw out when every frame is full.

A process references pages one at a time. If the page is already in a frame,
that is a hit. If not, it is a page fault: the page is loaded, and if no frame
is free, one resident page (the victim) is replaced.

    FIFO     throw out the page that was loaded earliest
    LRU      throw out the page that was used least recently
    Optimal  throw out the page whose next use is farthest away (needs the future; a benchmark)

Also here: the Belady check (does more frames ever mean more faults?), the
working set (pages used in the last `window` references) and the effective
access time with a TLB.
"""

import re

ALGORITHMS = ("fifo", "lru", "opt")

ALGORITHM_NAMES = {
    "fifo": "FIFO",
    "lru": "LRU",
    "opt": "Optimal",
}

MAX_REFS = 200
MAX_PAGE = 999
MAX_FRAMES = 12


def parse_refs(text):
    """Turn '7, 0, 1, 2' (or '7 0 1 2') into a list of page numbers."""
    tokens = [t for t in re.split(r"[\s,]+", (text or "").strip()) if t]
    if not tokens:
        raise ValueError("Give at least one page reference, for example 7, 0, 1, 2.")
    if len(tokens) > MAX_REFS:
        raise ValueError(f"A reference string can have at most {MAX_REFS} pages.")
    refs = []
    for tok in tokens:
        try:
            n = int(tok)
        except ValueError:
            raise ValueError(f"'{tok}' is not a whole number.")
        if not 0 <= n <= MAX_PAGE:
            raise ValueError(f"Page numbers must be between 0 and {MAX_PAGE}.")
        refs.append(n)
    return refs


def _victim(algorithm, slots, loaded_at, last_used, refs, t):
    """Choose which resident page to replace. slots is the list of frames (None = empty)."""
    resident = [(i, p) for i, p in enumerate(slots) if p is not None]
    if algorithm == "fifo":
        return min(resident, key=lambda ip: (loaded_at[ip[1]], ip[0]))[1]
    if algorithm == "lru":
        return min(resident, key=lambda ip: (last_used[ip[1]], ip[0]))[1]
    if algorithm == "opt":
        def next_use(page):
            for later in range(t + 1, len(refs)):
                if refs[later] == page:
                    return later
            return float("inf")  # never used again: the best thing to throw out
        # farthest next use wins; ties go to the earlier frame
        return max(resident, key=lambda ip: (next_use(ip[1]), -ip[0]))[1]
    raise ValueError(f"unknown algorithm: {algorithm}")


def simulate_pages(algorithm, refs, frames):
    """Run one replacement algorithm over the reference string with a fixed number of frames."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unknown algorithm: {algorithm}")
    if not 1 <= frames <= MAX_FRAMES:
        raise ValueError(f"Frames must be between 1 and {MAX_FRAMES}.")

    slots = [None] * frames
    loaded_at = {}
    last_used = {}
    steps = []
    faults = 0

    for t, page in enumerate(refs):
        if page in slots:
            fault = False
            victim = None
        else:
            fault = True
            faults += 1
            if None in slots:
                idx = slots.index(None)
                victim = None
            else:
                victim = _victim(algorithm, slots, loaded_at, last_used, refs, t)
                idx = slots.index(victim)
            slots[idx] = page
            loaded_at[page] = t
        last_used[page] = t
        steps.append({
            "t": t,
            "page": page,
            "fault": fault,
            "victim": victim,
            "frames": list(slots),
        })

    n = len(refs)
    return {
        "algorithm": algorithm,
        "name": ALGORITHM_NAMES[algorithm],
        "frames": frames,
        "steps": steps,
        "faults": faults,
        "hits": n - faults,
        "fault_rate": round(100 * faults / n, 1) if n else 0.0,
    }


def fault_table(refs, max_frames):
    """Fault counts for every algorithm, with 1..max_frames frames."""
    return {
        alg: [simulate_pages(alg, refs, f)["faults"] for f in range(1, max_frames + 1)]
        for alg in ALGORITHMS
    }


def belady_anomalies(counts):
    """Frame counts where adding a frame made a FIFO run fault MORE. Belady's anomaly."""
    fifo = counts["fifo"]
    return [i + 2 for i in range(len(fifo) - 1) if fifo[i + 1] > fifo[i]]


def working_set(refs, window):
    """Size of the working set at each reference: distinct pages among the last `window` references."""
    if window < 1:
        raise ValueError("The working-set window must be at least 1.")
    sizes = []
    for t in range(len(refs)):
        lo = max(0, t - window + 1)
        sizes.append(len(set(refs[lo:t + 1])))
    return sizes


def effective_access_time(tlb_hit_ratio, tlb_ns, mem_ns):
    """Average memory access time with a TLB and a single-level page table.

    TLB hit:  one TLB lookup + one memory access for the data.
    TLB miss: one TLB lookup + one memory access for the page table + one for the data.
    Page faults are not included here.
    """
    if not 0 <= tlb_hit_ratio <= 1:
        raise ValueError("The TLB hit ratio must be between 0 and 100 percent.")
    hit_time = tlb_ns + mem_ns
    miss_time = tlb_ns + 2 * mem_ns
    return round(tlb_hit_ratio * hit_time + (1 - tlb_hit_ratio) * miss_time, 2)


def analyse(refs, frames, window=None, tlb_hit_percent=None, tlb_ns=None, mem_ns=None):
    """Everything the page needs for one reference string, in one call."""
    results = {alg: simulate_pages(alg, refs, frames) for alg in ALGORITHMS}
    distinct = len(set(refs))
    max_frames = min(8, max(1, distinct))
    counts = fault_table(refs, max_frames)

    out = {
        "refs": refs,
        "frames": frames,
        "results": results,
        "belady": {
            "frames": list(range(1, max_frames + 1)),
            "faults": counts,
            "anomalies": belady_anomalies(counts),
        },
    }

    if window is not None:
        sizes = working_set(refs, window)
        out["working_set"] = {
            "window": window,
            "sizes": sizes,
            "max": max(sizes),
            # references where the working set does not fit in the frames: the thrashing warning sign
            "over_frames": sum(1 for s in sizes if s > frames),
        }

    if None not in (tlb_hit_percent, tlb_ns, mem_ns):
        out["tlb"] = {
            "hit_percent": tlb_hit_percent,
            "tlb_ns": tlb_ns,
            "mem_ns": mem_ns,
            "eat_ns": effective_access_time(tlb_hit_percent / 100, tlb_ns, mem_ns),
        }
    return out
