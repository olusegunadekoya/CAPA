/* CAPA Web — single-page front-end (vanilla JS, no build step) */
"use strict";

/* ------------------------------------------------------------------ util */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
  return data;
}

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

const STATUS_CLASS = {
  "Open": "st-open", "In Progress": "st-inprogress", "Verification": "st-verification",
  "Closed": "st-closed", "Overdue": "st-overdue",
};
const PRIORITY_CLASS = { Low: "pr-low", Medium: "pr-medium", High: "pr-high", Critical: "pr-critical" };
const STATUS_COLOR = {
  Open: "#4f8ef7", "In Progress": "#f5b942", Verification: "#a78bfa",
  Closed: "#3ecf8e", Overdue: "#f2607a",
};
const PRIORITY_COLOR = { Low: "#5da9e9", Medium: "#f5b942", High: "#f08c4b", Critical: "#f2607a" };

const statusPill = st => `<span class="pill ${STATUS_CLASS[st] || "st-open"}">${esc(st)}</span>`;
const priorityPill = p => `<span class="pill ${PRIORITY_CLASS[p] || "pr-medium"}">${esc(p)}</span>`;

function daysCell(c) {
  if (c.effective_status === "Overdue") {
    const late = c.days_remaining != null ? Math.abs(c.days_remaining) : null;
    return `<span class="num-days late">${late != null ? late + "d late" : "late"}</span>`;
  }
  if (c.status === "Closed") return `<span style="color:var(--muted)">closed</span>`;
  if (c.days_remaining == null) return "—";
  const d = c.days_remaining;
  const cls = d <= 3 ? "late" : d <= 14 ? "soon" : "fine";
  return `<span class="num-days ${cls}">${d === 0 ? "today" : d + "d left"}</span>`;
}

/* ---------------------------------------------------------------- state */
const S = {
  boot: null,
  view: "dashboard",      // dashboard | register | tasks | settings | detail
  detailId: null,
  detailTab: "record",
  reg: { search: "", status: "", priority: "", order: "target_date ASC" },
};

const TITLES = { dashboard: "Dashboard", register: "CAPA Register", tasks: "My Tasks",
                 settings: "Settings", detail: "CAPA Record" };

/* ------------------------------------------------------------- routing */
function nav(view, id = null) {
  S.view = view;
  S.detailId = id;
  S.detailTab = "record";
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#page-title").textContent = TITLES[view];
  render();
}

/* ------------------------------------------------------------ rendering */
async function render() {
  const view = $("#view");
  const actions = $("#topbar-actions");
  actions.innerHTML = "";
  try {
    if (S.view === "dashboard") await renderDashboard(view, actions);
    else if (S.view === "register") await renderRegister(view, actions);
    else if (S.view === "tasks") await renderTasks(view, actions);
    else if (S.view === "settings") await renderSettings(view, actions);
    else if (S.view === "detail") await renderDetail(view, actions);
  } catch (err) {
    view.innerHTML = `<div class="card"><h3>Error</h3><p>${esc(err.message)}</p></div>`;
  }
}

/* =========================================================== dashboard */
function donutSvg(counts, total) {
  const entries = Object.entries(counts).filter(([, v]) => v > 0);
  if (!total || !entries.length) {
    return `<svg viewBox="0 0 42 42" class="donut"><circle cx="21" cy="21" r="15.9"
      fill="none" stroke="#1e2c49" stroke-width="7"/></svg>`;
  }
  let offset = 25; // start at top
  const segs = entries.map(([k, v]) => {
    const pct = (v / total) * 100;
    const seg = `<circle cx="21" cy="21" r="15.9" fill="none"
      stroke="${STATUS_COLOR[k] || "#4f8ef7"}" stroke-width="7"
      stroke-dasharray="${pct.toFixed(2)} ${(100 - pct).toFixed(2)}"
      stroke-dashoffset="${offset.toFixed(2)}"/>`;
    offset -= pct;
    return seg;
  }).join("");
  return `<svg viewBox="0 0 42 42" style="width:190px;height:190px">${segs}
    <text x="21" y="20.2" text-anchor="middle" font-size="7" font-weight="800"
      fill="#e7edf8">${total}</text>
    <text x="21" y="25.6" text-anchor="middle" font-size="3" fill="#93a3c4">CAPAS</text>
  </svg>`;
}

function barList(counts, colors) {
  const max = Math.max(...Object.values(counts), 1);
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `
      <div class="bar-row">
        <span style="font-size:12px;color:var(--muted)">${esc(k)}</span>
        <div class="bar-track"><div class="bar-fill"
          style="width:${(v / max) * 100}%;background:${colors[k] || "#4f8ef7"}"></div></div>
        <b>${v}</b>
      </div>`).join("");
}

function miniTable(rows, emptyMsg) {
  if (!rows.length) return `<div class="empty">${esc(emptyMsg)}</div>`;
  return `<table class="reg"><tbody>${rows.map(c => `
    <tr data-open="${c.id}">
      <td><b style="color:var(--accent-2)">${esc(c.capa_number)}</b></td>
      <td class="wrap">${esc(c.title)}</td>
      <td>${statusPill(c.effective_status)}</td>
      <td>${daysCell(c)}</td>
    </tr>`).join("")}</tbody></table>`;
}

async function renderDashboard(view, actions) {
  actions.innerHTML = `<a class="btn btn-sm" href="/export/register.csv">⬇ Export register (.csv)</a>`;
  const m = await api("/api/metrics");
  const legend = Object.entries(m.by_status)
    .map(([k, v]) => `<div class="row"><span class="dot" style="background:${STATUS_COLOR[k]}"></span>
       ${esc(k)} <b style="margin-left:auto">${v}</b></div>`).join("");
  view.innerHTML = `
    <div class="grid-kpi">
      <div class="card kpi accent"><div class="num">${m.total}</div><div class="lbl">Total CAPAs</div></div>
      <div class="card kpi"><div class="num">${m.open + m.in_progress}</div><div class="lbl">Active</div></div>
      <div class="card kpi warn"><div class="num">${m.verification}</div><div class="lbl">In verification</div></div>
      <div class="card kpi danger"><div class="num">${m.overdue}</div><div class="lbl">Overdue</div></div>
      <div class="card kpi ok"><div class="num">${m.closed}</div><div class="lbl">Closed (${m.completion_rate}%)</div></div>
    </div>
    <div class="charts">
      <div class="card"><h3>Status mix</h3>
        <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
          ${donutSvg(m.by_status, m.total)}<div class="legend" style="flex:1;min-width:130px">${legend}</div>
        </div>
      </div>
      <div class="grid2">
        <div class="card"><h3>By priority</h3><div class="bars">${barList(m.by_priority, PRIORITY_COLOR)}</div></div>
        <div class="card"><h3>By source</h3><div class="bars">${barList(m.by_source, {})}</div></div>
      </div>
    </div>
    <div class="grid2">
      <div class="card"><h3>⚠ Overdue (${m.overdue_items.length})</h3>${miniTable(m.overdue_items, "Nothing overdue — great job.")}</div>
      <div class="card"><h3>🕒 Due within 14 days (${m.due_soon.length})</h3>${miniTable(m.due_soon, "Nothing due soon.")}</div>
    </div>`;
  bindOpenLinks(view);
}

function bindOpenLinks(root) {
  $$("[data-open]", root).forEach(el =>
    el.addEventListener("click", () => nav("detail", Number(el.dataset.open))));
}

/* ============================================================ register */
async function renderRegister(view, actions) {
  actions.innerHTML = `<a class="btn btn-sm" href="/export/register.csv">⬇ Export (.csv)</a>`;
  const q = S.reg;
  const rows = await api(`/api/capas?search=${encodeURIComponent(q.search)}` +
    `&status=${encodeURIComponent(q.status)}&priority=${encodeURIComponent(q.priority)}` +
    `&order=${encodeURIComponent(q.order)}`);

  const opt = (list, cur) => list.map(v =>
    `<option ${v === cur ? "selected" : ""}>${esc(v)}</option>`).join("");
  const sortTh = (key, label) => {
    const [curKey, curDir] = q.order.split(" ");
    const isCur = curKey === key;
    const cls = "sortable" + (isCur ? " sorted" + (curDir === "ASC" ? " asc" : "") : "");
    return `<th class="${cls}" data-sort="${key}">${esc(label)}</th>`;
  };

  view.innerHTML = `
    <div class="filters">
      <input type="search" id="reg-search" placeholder="Search number, title, product, owner…"
             value="${esc(q.search)}">
      <select id="reg-status">
        <option value="">All statuses</option>
        ${opt(["Open", "In Progress", "Verification", "Closed", "Overdue"], q.status)}
      </select>
      <select id="reg-priority">
        <option value="">All priorities</option>
        ${opt(["Critical", "High", "Medium", "Low"], q.priority)}
      </select>
      <button class="btn btn-sm" id="reg-clear">Clear</button>
    </div>
    <div class="card" style="padding:0;overflow:auto">
      <table class="reg">
        <thead><tr>
          ${sortTh("capa_number", "Number")}${sortTh("opened_on", "Opened")}
          <th>Title</th><th>Source</th><th>Product / Area</th><th>Owner</th>
          ${sortTh("priority", "Priority")}${sortTh("status", "Status")}
          ${sortTh("target_date", "Target / Timing")}
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map(c => `
            <tr data-open="${c.id}">
              <td><b style="color:var(--accent-2)">${esc(c.capa_number)}</b></td>
              <td>${fmtDate(c.opened_on)}</td>
              <td class="wrap">${esc(c.title)}</td>
              <td>${esc(c.source)}</td>
              <td class="wrap">${esc(c.product)}</td>
              <td>${esc(c.owner || "—")}</td>
              <td>${priorityPill(c.priority)}</td>
              <td>${statusPill(c.effective_status)}</td>
              <td>${fmtDate(c.target_date)} · ${daysCell(c)}</td>
            </tr>`).join("")
            : `<tr><td colspan="9"><div class="empty">No CAPAs match the current filters.</div></td></tr>`}
        </tbody>
      </table>
    </div>
    <p style="color:var(--muted);font-size:12px;margin-top:10px">${rows.length} record(s)</p>`;

  const search = $("#reg-search");
  let t;
  search.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(() => { S.reg.search = search.value.trim(); render(); }, 300);
  });
  $("#reg-status").addEventListener("change", e => { S.reg.status = e.target.value; render(); });
  $("#reg-priority").addEventListener("change", e => { S.reg.priority = e.target.value; render(); });
  $("#reg-clear").addEventListener("click", () => {
    S.reg = { ...S.reg, search: "", status: "", priority: "" }; render();
  });
  $$("th.sortable", view).forEach(th => th.addEventListener("click", () => {
    const key = th.dataset.sort;
    const [curKey, curDir] = S.reg.order.split(" ");
    S.reg.order = curKey === key && curDir === "ASC" ? `${key} DESC` : `${key} ASC`;
    render();
  }));
  bindOpenLinks(view);
}

/* =============================================================== tasks */
async function renderTasks(view, actions) {
  actions.innerHTML = "";
  const data = await api("/api/tasks");
  updateTaskBadge(data.counts);
  const groups = data.groups.map(g => `
    <div class="tgroup card">
      <h4 data-open="${g.items[0].capa_id}">${esc(g.capa)}</h4>
      <div class="task-list">
        ${g.items.map(t => taskRow(t, true)).join("")}
      </div>
    </div>`).join("");
  view.innerHTML = `
    <div class="grid-kpi">
      <div class="card kpi accent"><div class="num">${data.counts.open}</div><div class="lbl">Open</div></div>
      <div class="card kpi danger"><div class="num">${data.counts.overdue}</div><div class="lbl">Overdue</div></div>
      <div class="card kpi ok"><div class="num">${data.counts.done}</div><div class="lbl">Completed</div></div>
    </div>
    ${groups || `<div class="card"><div class="empty">No action-item tasks yet. Add tasks inside a CAPA record.</div></div>`}`;

  $$(".task-check", view).forEach(cb => cb.addEventListener("change", async () => {
    try {
      await api(`/api/task/${cb.dataset.id}`, { method: "PUT", body: { done: cb.checked } });
      toast(cb.checked ? "Task completed ✓" : "Task reopened");
      render();
    } catch (e) { toast(e.message, true); }
  }));
  $$(".task-del", view).forEach(btn => btn.addEventListener("click", async () => {
    if (!confirm("Delete this task?")) return;
    try { await api(`/api/task/${btn.dataset.id}`, { method: "DELETE" }); toast("Task deleted"); render(); }
    catch (e) { toast(e.message, true); }
  }));
  bindOpenLinks(view);
}

function taskRow(t, showCapaLink = false) {
  let due = "";
  if (t.due_date) {
    const cls = t.done ? "" : (t.state === "overdue" ? "late" : t.days <= 3 ? "soon" : "fine");
    due = `<span class="task-meta num-days ${cls}">due ${fmtDate(t.due_date)}${!t.done && t.days != null ? ` (${t.days < 0 ? -t.days + "d late" : t.days + "d"})` : ""}</span>`;
  }
  return `
    <div class="task-item ${t.done ? "done" : ""}">
      <input type="checkbox" class="task-check" data-id="${t.id}" ${t.done ? "checked" : ""}>
      <div class="task-desc">${esc(t.description)}
        ${t.assignee ? `<div class="task-meta">👤 ${esc(t.assignee)}</div>` : ""}</div>
      ${due}
      <button class="icon-btn task-del" data-id="${t.id}" title="Delete task">🗑</button>
    </div>`;
}

function updateTaskBadge(counts) {
  const badge = $("#task-badge");
  const n = counts.overdue + counts.open;
  badge.hidden = n === 0;
  badge.textContent = n;
}

/* ============================================================== detail */
async function renderDetail(view, actions) {
  const c = await api(`/api/capa/${S.detailId}`);
  actions.innerHTML = `
    <a class="btn btn-sm" href="/export/capa/${c.id}.txt">⬇ Report (.txt)</a>
    <button class="btn btn-sm btn-danger" id="del-capa">Delete</button>
    <button class="btn btn-sm" id="back-reg">← Back</button>`;
  $("#back-reg").addEventListener("click", () => nav("register"));
  $("#del-capa").addEventListener("click", async () => {
    if (!confirm(`Delete ${c.capa_number}? This cannot be undone.`)) return;
    try { await api(`/api/capa/${c.id}`, { method: "DELETE" }); toast("CAPA deleted"); nav("register"); }
    catch (e) { toast(e.message, true); }
  });

  const vocab = S.boot.vocab;
  view.innerHTML = `
    <div class="detail-head">
      <div style="min-width:0">
        <div style="color:var(--muted);font-weight:700">${esc(c.capa_number)}</div>
        <div class="detail-title">${esc(c.title)}</div>
        <div class="detail-meta">
          ${statusPill(c.effective_status)} ${priorityPill(c.priority)}
          <span>Opened ${fmtDate(c.opened_on)}</span>
          <span>Target ${fmtDate(c.target_date)}</span>
          ${c.closed_on ? `<span>Closed ${fmtDate(c.closed_on)}</span>` : `<span>${daysCell(c)}</span>`}
          <span>Owner: <b>${esc(c.owner || "—")}</b></span>
        </div>
      </div>
    </div>
    <div class="tabs">
      ${["record", "rca", "tasks", "docs", "activity", "report"].map(t =>
        `<button class="tab-btn ${S.detailTab === t ? "active" : ""}" data-tab="${t}">${
          { record: "Record", rca: "Root Cause & Actions", tasks: `Action Items (${c.tasks.length})`,
            docs: `Attachments (${c.documents.length})`, activity: `Activity (${c.events.length})`,
            report: "Report" }[t]}</button>`).join("")}
    </div>
    <div id="tab-body"></div>`;

  $$(".tab-btn", view).forEach(b => b.addEventListener("click", () => {
    S.detailTab = b.dataset.tab; renderDetailTab(c);
  }));
  renderDetailTab(c);
}

function selectHtml(name, options, current) {
  return `<select name="${name}">${options.map(o =>
    `<option ${o === current ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
}

function renderDetailTab(c) {
  const body = $("#tab-body");
  const V = S.boot.vocab;

  if (S.detailTab === "record" || S.detailTab === "rca") {
    const isRec = S.detailTab === "record";
    const fields = isRec ? `
        <label class="fld span2">Title<input name="title" value="${esc(c.title)}"></label>
        <label class="fld">Source${selectHtml("source", V.sources, c.source)}</label>
        <label class="fld">Priority${selectHtml("priority", V.priorities, c.priority)}</label>
        <label class="fld">Status${selectHtml("status", V.statuses, c.status)}</label>
        <label class="fld">Product / Area<input name="product" value="${esc(c.product)}"></label>
        <label class="fld">Site<input name="site" value="${esc(c.site)}"></label>
        <label class="fld">Originator<input name="originator" value="${esc(c.originator)}"></label>
        <label class="fld">CAPA owner<input name="owner" value="${esc(c.owner)}"></label>
        <label class="fld">Opened on<input type="date" name="opened_on" value="${esc(c.opened_on)}"></label>
        <label class="fld">Target date<input type="date" name="target_date" value="${esc(c.target_date)}"></label>
        <label class="fld">Closed on<input type="date" name="closed_on" value="${esc(c.closed_on || "")}"></label>
        <label class="fld span2">Problem statement<textarea name="problem_statement" rows="4">${esc(c.problem_statement)}</textarea></label>`
      : `
        <label class="fld span2">RCA method${selectHtml("root_cause_method", ["", ...V.rca_methods], c.root_cause_method)}</label>
        <label class="fld span2">Immediate containment<textarea name="containment" rows="3">${esc(c.containment)}</textarea></label>
        <label class="fld span2">Root cause<textarea name="root_cause" rows="3">${esc(c.root_cause)}</textarea></label>
        <label class="fld span2">Corrective action<textarea name="corrective_action" rows="3">${esc(c.corrective_action)}</textarea></label>
        <label class="fld span2">Preventive action<textarea name="preventive_action" rows="3">${esc(c.preventive_action)}</textarea></label>
        <label class="fld span2">Effectiveness check<textarea name="effectiveness_check" rows="3">${esc(c.effectiveness_check)}</textarea></label>`;

    body.innerHTML = `
      <form class="card" id="edit-form">
        <div class="form-grid">${fields}</div>
        <div class="save-bar">
          <button type="submit" class="btn btn-accent">💾 Save</button>
          <span class="dirty-flag" id="dirty" hidden>Unsaved changes</span>
        </div>
      </form>`;
    const form = $("#edit-form");
    form.addEventListener("input", () => { $("#dirty").hidden = false; });
    form.addEventListener("submit", async ev => {
      ev.preventDefault();
      const payload = Object.fromEntries(new FormData(form).entries());
      try {
        await api(`/api/capa/${c.id}`, { method: "PUT", body: payload });
        toast("Saved ✓");
        renderDetail($("#view"), $("#topbar-actions"));
      } catch (e) { toast(e.message, true); }
    });
    return;
  }

  if (S.detailTab === "tasks") {
    const prog = c.task_progress;
    const pct = prog.total ? Math.round(100 * prog.done / prog.total) : 0;
    body.innerHTML = `
      <div class="card">
        <h3>Action items — ${prog.done}/${prog.total} complete (${pct}%)</h3>
        <div class="bar-track" style="margin-bottom:14px">
          <div class="bar-fill" style="width:${pct}%;background:var(--ok)"></div></div>
        <div class="task-list">
          ${c.tasks.length ? c.tasks.map(t => taskRow({ ...t, state: t.done ? "done" : (t.due_date && t.due_date < S.boot.today ? "overdue" : "open") })).join("")
            : `<div class="empty">No action items yet.</div>`}
        </div>
        <form class="add-row" id="add-task">
          <input name="description" placeholder="New action item…" required>
          <input name="assignee" placeholder="Assignee">
          <input type="date" name="due_date">
          <button class="btn btn-accent">Add</button>
        </form>
      </div>`;
    $("#add-task").addEventListener("submit", async ev => {
      ev.preventDefault();
      const f = ev.target;
      try {
        await api(`/api/capa/${c.id}/task`, { method: "POST", body: Object.fromEntries(new FormData(f)) });
        toast("Task added"); renderDetail($("#view"), $("#topbar-actions"));
      } catch (e) { toast(e.message, true); }
    });
    $$(".task-check", body).forEach(cb => cb.addEventListener("change", async () => {
      try {
        await api(`/api/task/${cb.dataset.id}`, { method: "PUT", body: { done: cb.checked } });
        renderDetail($("#view"), $("#topbar-actions"));
      } catch (e) { toast(e.message, true); }
    }));
    $$(".task-del", body).forEach(btn => btn.addEventListener("click", async () => {
      if (!confirm("Delete task?")) return;
      try { await api(`/api/task/${btn.dataset.id}`, { method: "DELETE" }); renderDetail($("#view"), $("#topbar-actions")); }
      catch (e) { toast(e.message, true); }
    }));
    return;
  }

  if (S.detailTab === "docs") {
    body.innerHTML = `
      <div class="card">
        <h3>Attached documents</h3>
        <div class="task-list">
          ${c.documents.length ? c.documents.map(d => `
            <div class="task-item">
              <span>📎</span>
              <div class="task-desc">${esc(d.name)}
                <div class="task-meta">added ${fmtDate(d.added_on)}</div></div>
              <button class="icon-btn doc-del" data-id="${d.id}" title="Remove">🗑</button>
            </div>`).join("") : `<div class="empty">No attachments.</div>`}
        </div>
        <form class="add-row" id="add-doc" style="grid-template-columns:1fr auto">
          <input name="name" placeholder="Document name / reference (e.g. Deviation report DR-102.pdf)" required>
          <button class="btn btn-accent">Attach reference</button>
        </form>
        <p style="color:var(--muted);font-size:12px">Files stay in your own document management
        system or shared drive — CAPA Web stores the reference only.</p>
      </div>`;
    $("#add-doc").addEventListener("submit", async ev => {
      ev.preventDefault();
      try {
        await api(`/api/capa/${c.id}/document`, { method: "POST",
          body: { name: new FormData(ev.target).get("name") } });
        toast("Document attached"); renderDetail($("#view"), $("#topbar-actions"));
      } catch (e) { toast(e.message, true); }
    });
    $$(".doc-del", body).forEach(btn => btn.addEventListener("click", async () => {
      try { await api(`/api/document/${btn.dataset.id}`, { method: "DELETE" }); renderDetail($("#view"), $("#topbar-actions")); }
      catch (e) { toast(e.message, true); }
    }));
    return;
  }

  if (S.detailTab === "activity") {
    body.innerHTML = `
      <div class="card">
        <h3>Activity log &amp; comments</h3>
        <div class="timeline">
          ${c.events.length ? c.events.map(e => `
            <div class="tl-item"><span class="tl-dot"></span>
              <div class="tl-body">
                <div>${esc(e.body)}</div>
                <div class="tl-when">${esc(e.author)} · ${esc(e.ts)}</div>
              </div></div>`).join("") : `<div class="empty">No activity recorded.</div>`}
        </div>
        <form class="comment-form" id="add-comment">
          <input name="body" placeholder="Add a comment…" required>
          <button class="btn btn-accent">Post</button>
        </form>
      </div>`;
    $("#add-comment").addEventListener("submit", async ev => {
      ev.preventDefault();
      try {
        await api(`/api/capa/${c.id}/comment`, { method: "POST",
          body: Object.fromEntries(new FormData(ev.target)) });
        toast("Comment posted"); renderDetail($("#view"), $("#topbar-actions"));
      } catch (e) { toast(e.message, true); }
    });
    return;
  }

  if (S.detailTab === "report") {
    body.innerHTML = `
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="margin:0">CAPA report preview</h3>
          <a class="btn btn-sm btn-accent" href="/export/capa/${c.id}.txt">⬇ Download .txt</a>
        </div>
        <pre class="report-pre">${esc(c.report_text)}</pre>
      </div>`;
  }
}

/* ============================================================ settings */
async function renderSettings(view, actions) {
  actions.innerHTML = "";
  const s = S.boot.settings;
  view.innerHTML = `
    <form class="card" id="settings-form" style="max-width:640px">
      <h3>Organisation</h3>
      <div class="form-grid">
        <label class="fld span2">Company<input name="company" value="${esc(s.company)}"></label>
        <label class="fld span2">Default site<input name="site" value="${esc(s.site)}"></label>
        <label class="fld span2">QMS procedure reference<input name="qms_reference" value="${esc(s.qms_reference)}"></label>
        <label class="fld span2">Current user<input name="user" value="${esc(s.user)}"></label>
      </div>
      <div class="save-bar"><button class="btn btn-accent" type="submit">💾 Save settings</button></div>
    </form>
    <div class="card" style="max-width:640px;margin-top:16px">
      <h3>Data</h3>
      <p style="color:var(--muted)">The web app uses the same database file as the desktop app
      (created under your user profile, e.g. <code>%LOCALAPPDATA%\\CAPA\\capa.db</code> on Windows).
      Records you create in either interface appear in both.</p>
      <a class="btn btn-sm" href="/export/register.csv">⬇ Export full register (.csv)</a>
    </div>`;
  $("#settings-form").addEventListener("submit", async ev => {
    ev.preventDefault();
    try {
      const res = await api("/api/settings", { method: "PUT",
        body: Object.fromEntries(new FormData(ev.target)) });
      S.boot.settings = res.settings;
      $("#brand-company").textContent = res.settings.company;
      toast("Settings saved ✓");
    } catch (e) { toast(e.message, true); }
  });
}

/* ========================================================= new-CAPA modal */
function openModal() {
  const backdrop = $("#modal-backdrop");
  const form = $("#new-capa-form");
  form.reset();
  $("#modal-error").hidden = true;
  $("#f-source").innerHTML = S.boot.vocab.sources.map(v => `<option>${esc(v)}</option>`).join("");
  $("#f-priority").innerHTML = S.boot.vocab.priorities.map(v =>
    `<option ${v === "Medium" ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#f-site").value = S.boot.settings.site || "";
  $("#f-opened").value = S.boot.today;
  const def = new Date(Date.now() + 30 * 864e5);
  form.elements.target_date.value = def.toISOString().slice(0, 10);
  form.elements.originator.value = S.boot.settings.user || "";
  backdrop.hidden = false;
  form.elements.title.focus();
}

function closeModal() { $("#modal-backdrop").hidden = true; }

/* ================================================================= init */
async function init() {
  S.boot = await api("/api/bootstrap");
  $("#brand-company").textContent = S.boot.settings.company;

  $$(".nav-btn").forEach(b => b.addEventListener("click", () => nav(b.dataset.view)));
  $("#btn-new-capa").addEventListener("click", openModal);
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal-cancel").addEventListener("click", closeModal);
  $("#modal-backdrop").addEventListener("mousedown", e => {
    if (e.target === e.currentTarget) closeModal();
  });

  $("#new-capa-form").addEventListener("submit", async ev => {
    ev.preventDefault();
    const err = $("#modal-error");
    err.hidden = true;
    try {
      const payload = Object.fromEntries(new FormData(ev.target).entries());
      const res = await api("/api/capa", { method: "POST", body: payload });
      closeModal();
      toast(`${res.capa_number} created ✓`);
      nav("detail", res.id);
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  });

  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
      e.preventDefault(); openModal();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f" && S.view === "register") {
      e.preventDefault(); $("#reg-search")?.focus();
    }
    if (e.key === "Escape" && !$("#modal-backdrop").hidden) closeModal();
  });

  api("/api/tasks").then(d => updateTaskBadge(d.counts)).catch(() => {});
  nav("dashboard");
}

init().catch(err => {
  document.body.innerHTML = `<div style="padding:40px;font-family:sans-serif">
    <h2>Failed to start CAPA Web</h2><p>${esc(err.message)}</p></div>`;
});
