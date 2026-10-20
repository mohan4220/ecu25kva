// ECU simulator page: the event stream into charts and panels, and every
// control as one POST.
"use strict";

const $ = (id) => document.getElementById(id);
const COLS = ["t_ms", "rpm", "ecu_rpm", "state", "synced", "rail", "rail_set", "duty",
  "fuel", "load", "clt", "oil", "wdg", "starter", "ignition"];
const C = Object.fromEntries(COLS.map((c, i) => [c, i]));
const STATES = ["OFF", "WAIT", "CRANK", "RUN", "SHUTDOWN"];
const SPN = {27: "EGR position", 100: "Oil pressure", 102: "Boost", 110: "Coolant temperature",
  157: "Rail pressure", 190: "Engine speed", 628: "Calibration (EOL)", 636: "Crank position"};
const LAMPS = [["protect", 0x01], ["amber", 0x04], ["red", 0x10], ["mil", 0x40]];
const KEEP_S = 30;               // live charts scroll over the last 30 s

async function post(path, body) {
  const r = await fetch(path, {method: "POST", body});
  return {ok: r.ok, status: r.status, text: await r.text()};
}
const cmd = (line) => post("/cmd", line).then((r) => { if (!r.ok) logLine(r.text, true); });

// ---- charts -------------------------------------------------------------

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const series = (label, color, scale) => ({label, stroke: css(color), width: 1.5, ...(scale && {scale})});
const CHARTS = [
  {title: "Speed, rpm", cols: ["rpm", "ecu_rpm"], s: [series("engine", "--s1"), series("ECU", "--s2")]},
  {title: "Rail, bar", cols: ["rail", "rail_set"], s: [series("rail", "--s1"), series("setpoint", "--s2")]},
  {title: "Metering and fuel", cols: ["duty", "fuel"], s: [series("duty", "--s3", "duty"), series("fuel mg", "--s4", "mg")],
    axes: [{scale: "duty"}, {scale: "mg", side: 1}]},
  {title: "Load and state", cols: ["load", "state"], s: [series("load kW", "--s1", "kw"),
    {...series("state", "--s4", "st"), paths: uPlot.paths.stepped({align: 1}),
     value: (u, v) => v == null ? "-" : STATES[v] ?? v}],
    axes: [{scale: "kw"}, {scale: "st", side: 1, size: 84, values: (u, vs) => vs.map((v) => STATES[v] ?? "")}],
    scales: {st: {range: [0, 4]}}},
];
let plots = [];
let live = COLS.map(() => []);   // columns, last KEEP_S s
let viewing = null;              // a past run shown instead of live
let dirty = false;

function makeCharts() {
  const el = $("charts");
  el.innerHTML = "";
  const width = Math.max(300, el.clientWidth - 16);
  const axis = {stroke: css("--muted"), grid: {stroke: css("--grid")}, ticks: {stroke: css("--grid")}};
  plots = CHARTS.map((c) => {
    const axes = [{...axis}, ...(c.axes ?? [{}]).map((a) => ({...axis, size: 64, ...a}))];
    return new uPlot({
      title: c.title, width, height: 170,
      cursor: {sync: {key: "ecu"}},
      scales: {x: {time: false}, ...(c.scales ?? {})},
      series: [{label: "t s"}, ...c.s],
      axes,
    }, [[], ...c.cols.map(() => [])], el);
  });
  draw();
}

function draw() {
  const cols = viewing ?? live;
  const t = cols[C.t_ms].map((x) => x / 1000);
  CHARTS.forEach((c, i) => plots[i].setData([t, ...c.cols.map((n) => cols[C[n]])]));
}

function addRows(rows) {
  for (const r of rows) r.forEach((v, i) => live[i].push(v));
  const last = live[0][live[0].length - 1];
  const drop = live[0].findIndex((t) => t >= last - KEEP_S * 1000);
  if (drop > 0) live = live.map((col) => col.slice(drop));
  dirty = true;
  // the slider follows the load, unless it is being moved
  const n = live[C.load].length;
  if (n && document.activeElement !== $("load")) {
    $("load").value = live[C.load][n - 1];
    $("load-v").textContent = live[C.load][n - 1];
  }
}

function frame() {
  if (dirty && !viewing) { draw(); dirty = false; }
  requestAnimationFrame(frame);
}

function csvColumns(text, every = 10) {
  const out = COLS.map(() => []);
  text.split("\n").slice(1).forEach((l, i) => {
    if (!l || i % every) return;
    l.split(",").forEach((v, k) => out[k].push(Number(v)));
  });
  return out;
}

async function showRun(id) {
  const r = await fetch(`/runs/${encodeURIComponent(id)}/trace.csv`);
  if (!r.ok) return;
  viewing = csvColumns(await r.text());
  $("viewing-name").textContent = id;
  $("viewing").hidden = false;
  draw();
  const rep = await fetch(`/runs/${encodeURIComponent(id)}/report.txt`);
  if (rep.ok) showReportText(await rep.text());
}
$("back-live").onclick = () => { viewing = null; $("viewing").hidden = true; draw(); };

// ---- panels -------------------------------------------------------------

function logLine(text, err) {
  const li = document.createElement("li");
  li.textContent = text;
  if (err) li.className = "err";
  const ul = $("events");
  ul.prepend(li);
  while (ul.children.length > 300) ul.lastChild.remove();
}

function showDm1(d) {
  $("lamps").innerHTML = LAMPS.map(([n, bit]) =>
    `<span class="lamp ${n} ${d.lamps & bit ? "lit" : ""}">${n}</span>`).join("");
  $("dm1").innerHTML = d.dtcs.length
    ? d.dtcs.map(([s, f]) => `<tr><td>${s}</td><td>${f}</td><td>${SPN[s] ?? ""}</td></tr>`).join("")
    : `<tr><td colspan="3" class="hint">No active faults</td></tr>`;
}

function addCan(frames) {
  const tb = $("can");
  for (const f of frames) {
    const tr = document.createElement("tr");
    for (const v of [f.t, f.dir, f.id, f.data, f.name]) {
      const td = document.createElement("td");
      td.textContent = v;
      tr.append(td);
    }
    tb.prepend(tr);
  }
  while (tb.children.length > 200) tb.lastChild.remove();
}

function showReport(r) {
  const el = $("report");
  el.innerHTML = "";
  const h = document.createElement("p");
  const n = r.outcomes.filter((o) => o.pass).length;
  h.innerHTML = `<b></b> — ${r.outcomes.length ? `${n}/${r.outcomes.length} checks pass` : "no checks"}`;
  h.firstChild.textContent = r.name;
  el.append(h);
  const ul = document.createElement("ul");
  for (const o of r.outcomes) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="${o.pass ? "pass" : "fail"}">${o.pass ? "PASS" : "FAIL"}</span> <code></code> <span class="hint"></span>`;
    li.children[1].textContent = o.text;
    li.children[2].textContent = `found ${o.found}`;
    ul.append(li);
  }
  el.append(ul);
}

function showReportText(text) {
  const el = $("report");
  el.innerHTML = "<pre class='mono'></pre>";
  el.firstChild.textContent = text;
}

async function loadRuns() {
  const r = await fetch("/runs");
  if (!r.ok) return;
  const ul = $("runs");
  ul.innerHTML = "";
  for (const id of await r.json()) {
    const li = document.createElement("li");
    li.textContent = id;
    li.onclick = () => { location.hash = `run=${encodeURIComponent(id)}`; showRun(id); };
    ul.append(li);
  }
}

function showStatus(s) {
  const m = $("st-mode");
  m.textContent = s.mode;
  m.className = `pill ${s.mode}`;
  $("st-t").textContent = s.t.toFixed(1);
  const target = s.speed == null ? "max" : `${s.speed}×`;
  $("st-speed").textContent = s.mode === "running" && s.reached != null
    ? `speed ${target}, reached ${s.reached.toFixed(1)}×` : `speed ${target}`;
  $("st-fw").textContent = s.firmware;
  document.querySelectorAll("#speeds button").forEach((b) =>
    b.classList.toggle("on", b.dataset.speed === (s.speed == null ? "max" : String(s.speed))));
  const n = live[C.state].length;
  $("st-state").textContent = n ? STATES[live[C.state][n - 1]] : "-";
}

// ---- event stream -------------------------------------------------------

function connect() {
  const es = new EventSource("/events");
  es.addEventListener("rows", (e) => addRows(JSON.parse(e.data)));
  es.addEventListener("can", (e) => addCan(JSON.parse(e.data)));
  es.addEventListener("dm1", (e) => showDm1(JSON.parse(e.data)));
  es.addEventListener("status", (e) => showStatus(JSON.parse(e.data)));
  es.addEventListener("event", (e) => logLine(JSON.parse(e.data)));
  es.addEventListener("error", (e) => { if (e.data) logLine(JSON.parse(e.data), true); });
  es.addEventListener("report", (e) => {
    const r = JSON.parse(e.data);
    showReport(r);
    loadRuns();
    const id = r.folder.split(/[\\/]/).pop();
    if (id) showRun(id);   // the whole run, now it has ended
  });
}

// ---- controls -----------------------------------------------------------

document.querySelectorAll("[data-cmd]").forEach((b) => b.onclick = () => {
  if (b.dataset.cmd === "run" || b.dataset.cmd === "reset") live = COLS.map(() => []);
  cmd(b.dataset.cmd);
});
document.querySelectorAll("[data-speed]").forEach((b) => b.onclick = () => cmd(`speed ${b.dataset.speed}`));
document.querySelectorAll("[data-line]").forEach((b) => b.onclick = () => {
  if (b.dataset.line === "start" && $("st-mode").textContent === "stopped") live = COLS.map(() => []);
  cmd(b.dataset.line);
});
$("load").oninput = () => { $("load-v").textContent = $("load").value; };
$("load").onchange = () => cmd(`load ${$("load").value}`);
$("droop").onchange = () => cmd(`droop ${$("droop").checked ? "on" : "off"}`);
$("fault").onchange = () => { $("action").value = $("fault").value; };
$("action").value = $("fault").value;
$("apply").onclick = () => cmd($("action").value);
$("action").onkeydown = (e) => { if (e.key === "Enter") cmd($("action").value); };

// ---- scenario -----------------------------------------------------------

let scenarioName = "scenario";
const editor = $("editor");

async function loadLibrary() {
  const r = await fetch("/library");
  if (!r.ok) return;
  $("library").innerHTML = "";
  for (const e of await r.json()) {
    const o = document.createElement("option");
    o.value = o.textContent = e.name;
    $("library").append(o);
  }
}
$("lib-open").onclick = async () => {
  const name = $("library").value;
  const r = await fetch(`/library/${name}`);
  if (!r.ok) return;
  editor.value = await r.text();
  scenarioName = name.split("/").pop().replace(/\.seq$/, "");
  $("errors").innerHTML = "";
};

function openFile(f) {
  f.text().then((t) => { editor.value = t; scenarioName = f.name.replace(/\.(seq|txt)$/, ""); $("errors").innerHTML = ""; });
}
$("file").onchange = (e) => { if (e.target.files[0]) openFile(e.target.files[0]); e.target.value = ""; };
editor.ondragover = (e) => { e.preventDefault(); editor.classList.add("drop"); };
editor.ondragleave = () => editor.classList.remove("drop");
editor.ondrop = (e) => {
  e.preventDefault();
  editor.classList.remove("drop");
  if (e.dataTransfer.files[0]) openFile(e.dataTransfer.files[0]);
};

$("save").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([editor.value], {type: "text/plain"}));
  a.download = `${scenarioName}.seq`;
  a.click();
  URL.revokeObjectURL(a.href);
};

function selectLine(n) {
  const lines = editor.value.split("\n");
  const start = lines.slice(0, n - 1).join("\n").length + (n > 1 ? 1 : 0);
  editor.focus();
  editor.setSelectionRange(start, start + (lines[n - 1] ?? "").length);
}

$("run-script").onclick = async () => {
  const r = await post(`/scenario?name=${encodeURIComponent(scenarioName)}`, editor.value);
  const ul = $("errors");
  ul.innerHTML = "";
  if (r.ok) { live = COLS.map(() => []); viewing = null; $("viewing").hidden = true; return; }
  let errs;
  try { errs = JSON.parse(r.text); } catch { errs = [{line: 0, msg: r.text}]; }
  for (const e of errs) {
    const li = document.createElement("li");
    li.textContent = `line ${e.line}: ${e.msg}`;
    li.onclick = () => selectLine(e.line);
    ul.append(li);
  }
};

// ---- firmware -----------------------------------------------------------

$("fw-file").onchange = async (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (!f) return;
  const r = await fetch(`/firmware?name=${encodeURIComponent(f.name)}`, {method: "POST", body: f});
  const msg = $("fw-msg");
  if (r.ok) {
    const fw = await r.json();
    msg.textContent = `Loaded ${fw.name} (ABI ${fw.abi}). Load only firmware you trust: it runs on this computer.`;
  } else {
    msg.textContent = `Refused: ${await r.text()}`;
  }
};

// ---- start --------------------------------------------------------------

makeCharts();
let resize;
window.addEventListener("resize", () => { clearTimeout(resize); resize = setTimeout(makeCharts, 150); });
connect();
loadLibrary();
loadRuns();
requestAnimationFrame(frame);
// #run=<folder> opens that run, so a run can be linked to
if (location.hash.startsWith("#run=")) showRun(decodeURIComponent(location.hash.slice(5)));
