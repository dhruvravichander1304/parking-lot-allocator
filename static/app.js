// Frontend for the Parking Lot Allocator: three views (parking lot, cars leave, paging), all served by the Flask API.

const $ = (id) => document.getElementById(id);

const ORDER = ["first", "best", "worst", "next"];        // lot view and timeline view
const PAGE_ORDER = ["fifo", "lru", "opt"];              // paging view

function carColor(i) {
  // spread hues around the wheel so neighbouring cars look different
  return `hsl(${(i * 47 + 20) % 360} 70% 62%)`;
}

function parseList(text) {
  return text
    .split(/[\s,]+/)
    .filter(Boolean)
    .map((t) => Number(t));
}

function showError(msg, id = "error") {
  const el = $(id);
  el.textContent = msg || "";
  el.hidden = !msg;
}

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Something went wrong.");
  return body;
}

function postJson(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/* ---------- tabs ---------- */

const VIEWS = ["lot", "leave", "paging", "lane"];

function showView(name) {
  VIEWS.forEach((v) => { $(`view-${v}`).hidden = v !== name; });
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.view === name;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", String(on));
  });
}

function viewFromHash() {
  const h = location.hash.slice(1);
  return VIEWS.includes(h) ? h : "lot";
}

document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    showView(t.dataset.view);
    history.replaceState(null, "", `#${t.dataset.view}`);
  });
});

/* ---------- view 1: parking lot ---------- */

async function run() {
  showError("");
  const slots = parseList($("slots").value);
  const cars = parseList($("cars").value);
  if (slots.some(Number.isNaN) || cars.some(Number.isNaN)) {
    showError("Only numbers, separated by commas or spaces, please.");
    return;
  }
  try {
    const data = await postJson("/api/simulate", { slots, cars, split: $("split").checked });
    render(data);
  } catch (e) {
    showError(e.message);
  }
}

function render(data) {
  const { results, winners, slots, cars } = data;
  const maxSlot = Math.max(...slots);

  renderVerdict(results, winners, cars.length);
  renderLots(results, winners, maxSlot, cars.length);
  renderSummary(results, winners, cars.length);
  renderLog(results);
}

function renderVerdict(results, winners, nCars) {
  const el = $("verdict");
  const names = winners.map((w) => results[w].name);
  const m = results[winners[0]].metrics;
  let html;
  if (winners.length === ORDER.length) {
    html = `<strong>All four tie</strong> on this lot: each parks ${m.parked} of ${nCars} cars and wastes ${m.wasted} units.`;
  } else {
    html = `<strong>${names.join(" and ")}</strong> did best here: ${m.parked} of ${nCars} cars parked, ${m.wasted} units left unused.`;
  }
  el.innerHTML = html;
  el.hidden = false;
}

function renderLots(results, winners, maxSlot, nCars) {
  const wrap = $("lots");
  wrap.innerHTML = "";

  ORDER.forEach((key) => {
    const r = results[key];
    const m = r.metrics;
    const lot = document.createElement("article");
    lot.className = "lot" + (winners.includes(key) ? " winner" : "");

    lot.innerHTML = `
      <div class="lot-head">
        <h3>${r.name}</h3>
        ${winners.includes(key) ? '<span class="badge">best here</span>' : ""}
      </div>
      <div class="lot-meta"><b>${m.parked}/${nCars}</b> parked &middot; <b>${m.utilization}%</b> used &middot; <b>${m.wasted}</b> wasted</div>
    `;

    const asphalt = document.createElement("div");
    asphalt.className = "asphalt";

    // cars appear in the order they arrived, so delay each by its step number
    const delayFor = {};
    r.steps.forEach((s, idx) => { delayFor[s.car] = idx * 0.35; });

    r.slots.forEach((s) => {
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `<div class="row-label"><b>Slot ${s.id + 1}</b>${s.size}</div>`;

      const slot = document.createElement("div");
      slot.className = "slot" + (s.cars.length === 0 ? " empty" : "");
      slot.style.width = `${(s.size / maxSlot) * 100}%`;
      slot.title = `Slot ${s.id + 1}: size ${s.size}, free ${s.free}`;

      s.cars.forEach((c) => {
        const car = document.createElement("div");
        car.className = "car";
        car.style.width = `${(c.size / s.size) * 100}%`;
        car.style.background = carColor(c.car);
        car.style.animationDelay = `${delayFor[c.car] || 0}s`;
        car.textContent = `C${c.car + 1}`;
        car.title = `Car ${c.car + 1}, size ${c.size}`;
        slot.appendChild(car);
      });

      if (s.cars.length > 0 && s.free > 0) {
        const w = document.createElement("div");
        w.className = "waste" + (s.closed ? " closed" : "");
        w.textContent = s.free;
        w.title = s.closed ? `${s.free} units lost inside this slot` : `${s.free} units still free`;
        slot.appendChild(w);
      }

      row.appendChild(slot);
      asphalt.appendChild(row);
    });
    lot.appendChild(asphalt);

    const away = document.createElement("div");
    away.className = "turned-away";
    if (r.rejected.length) {
      away.innerHTML = "Turned away:" + r.rejected
        .map((c) => `<span class="chip">C${c.car + 1} &middot; ${c.size}</span>`)
        .join("");
    } else {
      away.textContent = "Every car found a slot.";
    }
    lot.appendChild(away);

    wrap.appendChild(lot);
  });

  const legend = $("legend");
  legend.hidden = false;
  legend.innerHTML = `
    <span><i style="background:${carColor(0)}"></i>car (C1, C2...)</span>
    <span><i style="background:repeating-linear-gradient(135deg, rgba(239,107,107,.5) 0 3px, rgba(239,107,107,.15) 3px 6px)"></i>lost inside a used slot</span>
    <span><i style="border:1px dashed #f2c230"></i>slot, drawn to scale</span>
  `;
}

function renderSummary(results, winners, nCars) {
  $("summaryWrap").hidden = false;

  const rows = [
    ["Cars parked", (m) => m.parked, "max"],
    ["Cars turned away", (m) => m.rejected, "min"],
    ["Space used", (m) => m.used, "max"],
    ["Utilization", (m) => m.utilization + "%", null, (m) => m.utilization, "max"],
    ["Wasted space", (m) => m.wasted, "min"],
    ["Internal fragmentation", (m) => m.internal_fragmentation, null],
    ["Free but unusable (external)", (m) => m.external_fragmentation, null],
  ];

  let html = "<thead><tr><th>Metric</th>" +
    ORDER.map((k) => `<th>${results[k].name}</th>`).join("") + "</tr></thead><tbody>";

  rows.forEach(([label, fmt, goal, num, numGoal]) => {
    const g = numGoal || goal;
    const vals = ORDER.map((k) => (num ? num(results[k].metrics) : fmt(results[k].metrics)));
    let target = null;
    if (g) {
      const nums = vals.map(Number);
      target = g === "max" ? Math.max(...nums) : Math.min(...nums);
    }
    html += `<tr><td>${label}</td>` + ORDER.map((k, i) => {
      const display = fmt(results[k].metrics);
      const best = g && Number(vals[i]) === target && new Set(vals.map(Number)).size > 1;
      return `<td class="mono${best ? " best" : ""}">${display}</td>`;
    }).join("") + "</tr>";
  });
  html += "</tbody>";
  $("summary").innerHTML = html;

  // utilization bars
  const bars = $("bars");
  bars.innerHTML = '<div class="bars-title">Space utilization</div>' + ORDER.map((k) => {
    const u = results[k].metrics.utilization;
    return `<div class="bar-row"><span>${results[k].name}</span>
      <div class="bar-track"><div class="bar-fill" style="width:0%" data-w="${u}"></div></div>
      <span class="v">${u}%</span></div>`;
  }).join("");
  requestAnimationFrame(() => {
    bars.querySelectorAll(".bar-fill").forEach((b) => { b.style.width = b.dataset.w + "%"; });
  });
}

function renderLog(results) {
  $("logWrap").hidden = false;
  $("log").innerHTML = ORDER.map((k) => {
    const items = results[k].steps
      .map((s) => `<li class="${s.slot === null ? "rej" : ""}">${s.text}</li>`)
      .join("");
    return `<div><h3>${results[k].name}</h3><ol>${items}</ol></div>`;
  }).join("");
}

async function loadInto(path) {
  showError("");
  try {
    const d = await api(path);
    $("slots").value = d.slots.join(", ");
    $("cars").value = d.cars.join(", ");
    await run();
  } catch (e) {
    showError(e.message);
  }
}

/* ---------- view 2: cars arrive and leave ---------- */

function memoryBar(snap, memory) {
  // one strip for the whole memory: parked cars and free holes, drawn to scale
  const bar = document.createElement("div");
  bar.className = "mem";
  const items = [
    ...snap.blocks.map((b) => ({ kind: "car", start: b.start, size: b.size, car: b.car })),
    ...snap.holes.map((h) => ({ kind: "hole", start: h.start, size: h.size })),
  ].sort((a, b) => a.start - b.start);

  items.forEach((it) => {
    const el = document.createElement("div");
    const wide = it.size / memory > 0.07;
    el.className = it.kind === "car" ? "mem-car" : "mem-hole";
    el.style.width = `${(it.size / memory) * 100}%`;
    if (it.kind === "car") {
      el.style.background = carColor(it.car);
      el.textContent = wide ? `C${it.car + 1}` : "";
      el.title = `Car ${it.car + 1}: ${it.size} units at address ${it.start}`;
    } else {
      el.textContent = wide ? `${it.size} free` : "";
      el.title = `Free hole: ${it.size} units at address ${it.start}`;
    }
    bar.appendChild(el);
  });
  return bar;
}

async function runLeave() {
  showError("", "leave-error");
  const memory = parseInt($("memory").value, 10);
  if (Number.isNaN(memory)) {
    showError("Memory size must be a whole number.", "leave-error");
    return;
  }
  try {
    const data = await postJson("/api/timeline", {
      memory,
      script: $("script").value,
      compact: $("compact").checked,
    });
    renderLeave(data);
  } catch (e) {
    showError(e.message, "leave-error");
  }
}

function renderLeave(data) {
  const { results, winners, memory, events } = data;
  const arrivals = events.filter((e) => e.op === "arrive").length;
  const names = winners.map((w) => results[w].name);
  const m = results[winners[0]].metrics;

  const verdict = $("leave-verdict");
  verdict.innerHTML = winners.length === ORDER.length
    ? `<strong>All four tie</strong> on this script: each parks ${m.parked} of ${arrivals} cars.`
    : `<strong>${names.join(" and ")}</strong> parked the most cars: ${m.parked} of ${arrivals}, with ${m.turned_away} turned away.`;
  verdict.hidden = false;

  const wrap = $("leave-results");
  wrap.innerHTML = "";
  ORDER.forEach((key) => {
    const r = results[key];
    const rm = r.metrics;
    const card = document.createElement("article");
    card.className = "lot" + (winners.includes(key) ? " winner" : "");

    const ext = rm.external_rejections
      ? ` (<b>${rm.external_rejections}</b> from external fragmentation)`
      : "";
    card.innerHTML = `
      <div class="lot-head">
        <h3>${r.name}</h3>
        ${winners.includes(key) ? '<span class="badge">parked most</span>' : ""}
      </div>
      <div class="lot-meta"><b>${rm.parked}</b> parked &middot; <b>${rm.turned_away}</b> turned away${ext} &middot; <b>${rm.compactions}</b> compactions${rm.cars_moved ? ` (${rm.cars_moved} cars moved)` : ""}</div>
      <div class="lot-meta">Ends with <b>${rm.holes_now}</b> hole${rm.holes_now === 1 ? "" : "s"}, largest <b>${rm.largest_hole_now}</b>, <b>${rm.utilization}%</b> of memory in use.</div>
    `;

    const steps = document.createElement("ol");
    steps.className = "steps";
    r.steps.forEach((s, i) => {
      const li = document.createElement("li");
      li.className = "step" + (s.placed === false ? " rej" : "");
      const text = document.createElement("div");
      text.className = "step-text";
      text.textContent = `${i + 1}. ${s.text}`;
      li.appendChild(text);
      li.appendChild(memoryBar(s.memory, memory));
      steps.appendChild(li);
    });
    card.appendChild(steps);
    wrap.appendChild(card);
  });
}

/* ---------- view 3: paging ---------- */

function frameTable(r, refs) {
  // textbook layout: one column per reference, one row per frame
  const wrap = document.createElement("div");
  wrap.className = "table-scroll";
  const t = document.createElement("table");
  t.className = "frames";

  let html = `<thead><tr><th>Page</th>${refs.map((p) => `<th>${p}</th>`).join("")}</tr></thead><tbody>`;
  for (let f = 0; f < r.frames; f++) {
    html += `<tr><th class="frame-label">Frame ${f + 1}</th>`;
    r.steps.forEach((s) => {
      const v = s.frames[f];
      const isNew = s.fault && v === s.page;
      html += `<td class="${isNew ? "new" : ""}">${v === null ? "-" : v}</td>`;
    });
    html += "</tr>";
  }
  html += `<tr class="victim-row"><th>Replaced</th>${r.steps.map((s) => `<td>${s.victim === null ? "" : s.victim}</td>`).join("")}</tr>`;
  html += `<tr class="fault-row"><th>Fault?</th>${r.steps.map((s) => `<td class="${s.fault ? "fault" : ""}">${s.fault ? "F" : ""}</td>`).join("")}</tr>`;
  html += "</tbody>";
  t.innerHTML = html;
  wrap.appendChild(t);
  return wrap;
}

async function runPaging() {
  showError("", "pg-error");
  try {
    const data = await postJson("/api/paging", {
      refs: $("refs").value,
      frames: $("frames").value,
      window: $("window").value,
      tlb_hit: $("tlb_hit").value,
      tlb_ns: $("tlb_ns").value,
      mem_ns: $("mem_ns").value,
    });
    renderPaging(data);
  } catch (e) {
    showError(e.message, "pg-error");
  }
}

function renderPaging(data) {
  const { results, refs, frames } = data;
  const faults = Object.fromEntries(PAGE_ORDER.map((k) => [k, results[k].faults]));
  const best = Math.min(...Object.values(faults));
  const winners = PAGE_ORDER.filter((k) => faults[k] === best);

  const verdict = $("pg-verdict");
  const summary = PAGE_ORDER.map((k) => `${results[k].name} ${faults[k]}`).join(" &middot; ");
  verdict.innerHTML = winners.length === PAGE_ORDER.length
    ? `<strong>All three tie</strong> with ${frames} frame${frames === 1 ? "" : "s"}: ${best} page faults each.`
    : `<strong>${winners.map((k) => results[k].name).join(" and ")}</strong> ${winners.length === 1 ? "has" : "have"} the fewest faults with ${frames} frame${frames === 1 ? "" : "s"}: ${best} of ${refs.length} references. Faults: ${summary}.`;
  verdict.hidden = false;

  const wrap = $("pg-results");
  wrap.innerHTML = "";
  PAGE_ORDER.forEach((key) => {
    const r = results[key];
    const card = document.createElement("article");
    card.className = "lot wide" + (winners.includes(key) ? " winner" : "");
    card.innerHTML = `
      <div class="lot-head">
        <h3>${r.name}</h3>
        ${winners.includes(key) ? '<span class="badge">fewest faults</span>' : ""}
      </div>
      <div class="lot-meta"><b>${r.faults}</b> faults &middot; <b>${r.hits}</b> hits &middot; <b>${r.fault_rate}%</b> of references fault</div>
    `;
    card.appendChild(frameTable(r, refs));
    wrap.appendChild(card);
  });

  renderBelady(data);
  renderWorkingSet(data);
}

function renderBelady(data) {
  const card = $("pg-belady-card");
  const b = data.belady;
  const anomalies = b.anomalies;
  const note = anomalies.length
    ? `With FIFO, going from ${anomalies[0] - 1} to ${anomalies[0]} frames <b>raised</b> the number of faults from ${b.faults.fifo[anomalies[0] - 2]} to ${b.faults.fifo[anomalies[0] - 1]}. This is Belady's anomaly. LRU and Optimal never get worse when given more frames.`
    : `On this reference string FIFO never gets worse with more frames. Belady's anomaly needs a special string, so try the Belady example button above.`;

  const rows = b.frames.map((f, i) => {
    const bad = anomalies.includes(f);
    return `<tr><th>${f}</th>` + PAGE_ORDER.map((k) => {
      const cls = k === "fifo" && bad ? ' class="bad"' : "";
      return `<td${cls}>${b.faults[k][i]}</td>`;
    }).join("") + "</tr>";
  }).join("");

  card.hidden = false;
  card.innerHTML = `
    <h2>Does more memory always help?</h2>
    <p class="note">Page faults for every number of frames, on the same reference string.</p>
    <div class="table-scroll">
      <table class="belady">
        <thead><tr><th>Frames</th>${PAGE_ORDER.map((k) => `<th>${data.results[k].name}</th>`).join("")}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="note">${note}</p>
  `;
}

function renderWorkingSet(data) {
  const card = $("pg-ws-card");
  const ws = data.working_set;
  const tlb = data.tlb;
  if (!ws && !tlb) {
    card.hidden = true;
    card.innerHTML = "";
    return;
  }

  let html = "<h2>Working set and TLB</h2>";
  if (ws) {
    const cells = ws.sizes.map((s, i) => {
      const over = s > data.frames;
      return `<td class="${over ? "over" : ""}">${s}</td>`;
    }).join("");
    html += `
      <p class="note">The working set at a reference is the set of distinct pages used in the last <b>${ws.window}</b> references. It is at most <b>${ws.max}</b> pages here. Red cells are where it is bigger than the <b>${data.frames}</b> frames.</p>
      <div class="table-scroll">
        <table class="frames">
          <thead><tr><th>Page</th>${data.refs.map((p) => `<th>${p}</th>`).join("")}</tr></thead>
          <tbody><tr><th>Working set</th>${cells}</tr></tbody>
        </table>
      </div>
      <p class="note">${ws.over_frames
        ? `For ${ws.over_frames} of ${data.refs.length} references the working set does not fit in memory. Sustained over long stretches, that is thrashing: the process spends its time faulting instead of working.`
        : `The working set always fits in the frames here, so this process should not thrash.`}</p>
    `;
  }
  if (tlb) {
    html += `<p class="note">With a TLB hit ratio of <b>${tlb.hit_percent}%</b>, a TLB lookup of <b>${tlb.tlb_ns} ns</b> and a memory access of <b>${tlb.mem_ns} ns</b>, the average memory access takes <b>${tlb.eat_ns} ns</b>, not counting page faults.</p>`;
  }
  card.hidden = false;
  card.innerHTML = html;
}

/* ---------- wiring ---------- */

$("run").addEventListener("click", run);
$("sample").addEventListener("click", () => loadInto("/api/sample"));
$("random").addEventListener("click", () => loadInto("/api/random"));
$("split").addEventListener("change", run);
["slots", "cars"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") run(); })
);

$("leave-run").addEventListener("click", runLeave);
$("leave-example").addEventListener("click", () => {
  $("memory").value = "1000";
  $("script").value = "300, 250, 250, -1, 100, 200, 200, -6, 200, 150";
  $("compact").checked = false;
  runLeave();
});
["memory", "script"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") runLeave(); })
);

$("pg-run").addEventListener("click", runPaging);
$("pg-example").addEventListener("click", () => {
  $("refs").value = "7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1";
  $("frames").value = "3";
  $("window").value = "4";
  runPaging();
});
$("pg-belady").addEventListener("click", () => {
  $("refs").value = "1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5";
  $("frames").value = "4";
  $("window").value = "4";
  runPaging();
});
["refs", "frames", "window", "tlb_hit", "tlb_ns", "mem_ns"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") runPaging(); })
);

/* ---------- view 4: car lane (blocking, deadlock, animated removal) ---------- */

let laneTimers = [];

function clearLaneTimers() {
  laneTimers.forEach(clearTimeout);
  laneTimers = [];
}

function drawLane(layout, cycle = []) {
  const strip = $("lane-strip");
  strip.innerHTML = "";
  const gateL = document.createElement("span");
  gateL.className = "gate";
  gateL.textContent = "LEFT GATE";
  strip.appendChild(gateL);
  layout.forEach((c) => {
    const el = document.createElement("div");
    el.className = "lane-car"
      + (c.waits_for.length ? " waiting" : "")
      + (cycle.includes(c.car) ? " deadlock" : "");
    el.dataset.car = c.car;
    const wait = c.waits_for.length ? "waits for " + c.waits_for.join(", ") : "free to leave";
    el.innerHTML = `<b>${c.car}</b><small>position ${c.position}</small><small>exit ${c.exit === "left" ? "left" : "right"}</small><small class="wait">${wait}</small>`;
    strip.appendChild(el);
  });
  const gateR = document.createElement("span");
  gateR.className = "gate";
  gateR.textContent = "RIGHT GATE";
  strip.appendChild(gateR);
}

async function runLane() {
  showError("", "lane-error");
  clearLaneTimers();
  try {
    const data = await postJson("/api/lane", {
      lane: $("lane").value,
      requests: $("requests").value,
    });
    renderLane(data);
  } catch (e) {
    showError(e.message, "lane-error");
  }
}

function renderLane(data) {
  const dl = data.deadlock;
  const verdict = $("lane-verdict");
  verdict.hidden = false;
  verdict.innerHTML = dl
    ? `<strong>Deadlock.</strong> ${dl.cycle.slice(0, -1).join(" and ")} block each other, so none can move. Nothing was moved.`
    : `<strong>No deadlock.</strong> ${data.steps.length} step${data.steps.length === 1 ? "" : "s"} to move ${$("requests").value.trim()} out. Each car leaves only when the way is clear.`;

  $("lane-before").textContent = "Before:  " + data.before.layout_text;
  drawLane(data.before.layout, dl ? dl.cycle : []);
  $("lane-now").textContent = "Now:     " + data.before.layout_text;
  $("lane-table").innerHTML = "<ol class=\"steps-list\"></ol>";
  animateLane(data, 0);
}

function animateLane(data, i) {
  if (i >= data.steps.length) {
    $("lane-now").textContent = "Final:   " + data.after.layout_text;
    return;
  }
  const step = data.steps[i];
  const el = document.querySelector(`.lane-car[data-car="${step.car}"]`);
  if (el && !step.deadlock) el.classList.add("leaving");   // the car slides out
  laneTimers.push(setTimeout(() => {
    const log = document.querySelector(".steps-list");
    if (log) {
      const li = document.createElement("li");
      li.textContent = step.text;
      if (step.deadlock) li.className = "rej";
      log.appendChild(li);
    }
    drawLane(step.layout, step.deadlock ? data.deadlock.cycle : []);
    $("lane-now").textContent = `Step ${i + 1}: ` + step.layout_text;
    laneTimers.push(setTimeout(() => animateLane(data, i + 1), 800));
  }, 700));
}

$("lane-run").addEventListener("click", runLane);
$("lane-example").addEventListener("click", () => {
  $("lane").value = "C<, A<";
  $("requests").value = "A";
  runLane();
});
$("lane-deadlock").addEventListener("click", () => {
  $("lane").value = "B>, A<";
  $("requests").value = "A";
  runLane();
});
["lane", "requests"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") runLane(); })
);

showView(viewFromHash());
run();
runLeave();
runPaging();
runLane();
