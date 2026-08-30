// ContinuumX Team 3 monitoring dashboard.
// Streams live events over the /ws/monitor WebSocket and polls REST snapshots.

const state = {
  agents: new Map(),
  errorCount: 0,
  errors: [],
  errorFilter: { agent: "all", severity: "all" },
  approvalPage: 0,
};

const $ = (id) => document.getElementById(id);

function fmtTs(ts) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function isHumanReviewed(audit) {
  const status = `${audit.verification_status || ""} ${audit.accuracy_grade || ""}`.toLowerCase();
  const amended = Number(audit.amended_cells_count || 0);
  if (audit.is_learned_pattern_applied && amended === 0) return true;
  if (amended > 0) return true;
  return /ground truth|human corrected|human_verified|human_amended/.test(status);
}

// ---- Fleet status doughnut ----
let statusChart;
let errorChart;
let accuracyChart;

function initChart() {
  const legend = {
    position: "bottom",
    labels: { color: "#8b9bb0", boxWidth: 10, padding: 12, font: { size: 11 } },
  };
  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
  };

  const ctx = $("statusChart").getContext("2d");
  statusChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Idle", "Busy", "Offline"],
      datasets: [{
        data: [0, 0, 0],
        backgroundColor: ["#34d399", "#fbbf24", "#f87171"],
        borderColor: "#121a27",
        borderWidth: 3,
      }],
    },
    options: {
      ...chartOpts,
      cutout: "68%",
      layout: { padding: 4 },
      plugins: { legend },
    },
  });

  const errCtx = $("errorChart").getContext("2d");
  errorChart = new Chart(errCtx, {
    type: "bar",
    data: { labels: [], datasets: [{ label: "Incidents", data: [], backgroundColor: "#f87171" }] },
    options: {
      ...chartOpts,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b9bb0", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "#8b9bb0", font: { size: 10 } }, grid: { color: "#243044" }, beginAtZero: true },
      },
    },
  });

  const accCtx = $("accuracyChart").getContext("2d");
  accuracyChart = new Chart(accCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: "Human-reviewed accuracy %",
        data: [],
        borderColor: "#34d399",
        backgroundColor: "rgba(52,211,153,.12)",
        fill: true,
        tension: 0.25,
        pointRadius: 3,
      }],
    },
    options: {
      ...chartOpts,
      plugins: { legend },
      scales: {
        x: { ticks: { color: "#8b9bb0", font: { size: 10 } }, grid: { color: "#243044" } },
        y: { min: 0, max: 100, ticks: { color: "#8b9bb0", font: { size: 10 } }, grid: { color: "#243044" } },
      },
    },
  });
}

function renderAgents() {
  const agents = [...state.agents.values()];
  const container = $("agents");
  const scrollTop = container.scrollTop;
  container.innerHTML = "";

  let online = 0, busy = 0, offline = 0, onHold = 0;
  const counts = { idle: 0, busy: 0, offline: 0 };

  for (const a of agents.sort((x, y) => x.agent_id.localeCompare(y.agent_id))) {
    counts[a.status] = (counts[a.status] || 0) + 1;
    if (a.status === "offline") offline++; else online++;
    if (a.status === "busy") busy++;
    onHold += a.tasks_on_hold || 0;

    const cpuHot = (a.cpu_percent || 0) > 80 ? "hot" : "";
    const memHot = (a.mem_percent || 0) > 80 ? "hot" : "";
    const confPct = Math.round((a.avg_confidence || 0) * 100);
    const accPending = !!a.accuracy_pending;
    const accLabel = accPending ? "pending" : `${(a.accuracy_pct || 0).toFixed(0)}%`;
    const accWidth = accPending ? 0 : (a.accuracy_pct || 0);

    const card = document.createElement("div");
    card.className = `agent-card status-${a.status}`;
    card.innerHTML = `
      <div class="agent-head">
        <div><div class="agent-id">${escapeHtml(a.agent_id)}</div><div class="agent-role">${escapeHtml(a.role || "")}</div></div>
        <span class="pill ${a.status}">${escapeHtml(a.status)}</span>
      </div>
      <div class="tasks">
        <span>run<b>${a.tasks_running || 0}</b></span>
        <span>queue<b>${a.tasks_queued || 0}</b></span>
        <span>hold<b>${a.tasks_on_hold || 0}</b></span>
        <span>done<b>${a.tasks_done || 0}</b></span>
        <span>rev<b>${a.reviewed_n || 0}</b></span>
      </div>
      <div class="meter-grid">
        <div class="meter">
          <div class="meter-label"><span>Confidence</span><span>${confPct}%</span></div>
          <div class="meter-bar"><div class="meter-fill" style="width:${confPct}%"></div></div>
        </div>
        <div class="meter">
          <div class="meter-label"><span>Accuracy</span><span>${accLabel}</span></div>
          <div class="meter-bar"><div class="meter-fill ok" style="width:${accWidth}%"></div></div>
        </div>
        <div class="meter">
          <div class="meter-label"><span>CPU</span><span>${(a.cpu_percent || 0).toFixed(0)}%</span></div>
          <div class="meter-bar"><div class="meter-fill ${cpuHot}" style="width:${a.cpu_percent || 0}%"></div></div>
        </div>
        <div class="meter">
          <div class="meter-label"><span>Memory</span><span>${(a.mem_percent || 0).toFixed(0)}%</span></div>
          <div class="meter-bar"><div class="meter-fill ${memHot}" style="width:${a.mem_percent || 0}%"></div></div>
        </div>
      </div>`;
    container.appendChild(card);
  }

  if (agents.length === 0) {
    container.innerHTML = '<div class="empty">No agents registered yet. Start the ContinuumX launcher or a demo agent.</div>';
  } else {
    container.scrollTop = scrollTop;
  }

  $("stat-total").textContent = agents.length;
  $("stat-online").textContent = online;
  $("stat-busy").textContent = busy;
  $("stat-offline").textContent = offline;
  $("stat-onhold").textContent = onHold;

  if (statusChart) {
    statusChart.data.datasets[0].data = [counts.idle, counts.busy, counts.offline];
    statusChart.update("none");
  }
  const caption = $("fleet-caption");
  if (caption) {
    caption.textContent = agents.length
      ? `${counts.idle || 0} idle · ${counts.busy || 0} busy · ${counts.offline || 0} offline`
      : "Waiting for agents…";
  }
}

function appendLog(targetId, event, isError) {
  const el = $(targetId);
  if (!el) return;
  const line = document.createElement("div");
  line.className = "log-line" + (isError ? " err" : "");
  const type = event.event_type || event.msg_type || event.channel || "EVENT";
  const detail = [];
  if (event.agent_id) detail.push(event.agent_id);
  if (event.from && event.to) detail.push(`${event.from} -> ${event.to}`);
  if (event.status) detail.push(event.status);
  if (event.detail) detail.push(event.detail);
  line.innerHTML = `<span class="ts">${fmtTs(event.timestamp)}</span><span class="type">${escapeHtml(type)}</span> ${escapeHtml(detail.join(" | "))}`;
  el.prepend(line);
  while (el.childNodes.length > 200) el.removeChild(el.lastChild);
}

function upsertError(row) {
  if (!row) return;
  const key = row.error_id || `${row.ts}|${row.category}|${row.message}`;
  row._key = key;
  const idx = state.errors.findIndex((e) => e._key === key);
  if (idx >= 0) state.errors[idx] = row;
  else state.errors.unshift(row);
  state.errors = state.errors.slice(0, 200);
  state.errorCount = state.errors.length;
  $("stat-errors").textContent = state.errorCount;
  renderErrorTable();
}

function normalizeIncident(raw) {
  if (!raw) return null;
  return {
    ts: raw.timestamp || "",
    agent: raw.agent_id || raw.module || "unknown",
    category: raw.error_type || raw.error_category || raw.event_type || "ERROR",
    rfq: raw.rfq_number || raw.transaction_uuid || "N/A",
    severity: raw.severity || "ERROR",
    status: raw.status || "",
    message: raw.detail || raw.error_message || "",
    error_id: raw.error_id || "",
  };
}

function renderErrorTable() {
  const body = $("error-rows");
  const { agent, severity } = state.errorFilter;
  const rows = state.errors.filter((e) => {
    if (agent !== "all" && e.agent !== agent) return false;
    if (severity !== "all" && String(e.severity).toUpperCase() !== severity) return false;
    return true;
  });
  body.innerHTML = "";
  if (rows.length === 0) {
    body.innerHTML = '<tr><td colspan="7" class="empty">No matching incidents.</td></tr>';
  } else {
    for (const row of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(fmtTs(row.ts) || row.ts)}</td>
        <td>${escapeHtml(row.agent)}</td>
        <td>${escapeHtml(row.category)}</td>
        <td>${escapeHtml(row.rfq)}</td>
        <td><span class="pill ${String(row.severity).toLowerCase() === "warning" ? "busy" : "offline"}">${escapeHtml(row.severity)}</span></td>
        <td>${escapeHtml(row.status)}</td>
        <td class="msg" title="${escapeHtml(row.message)}">${escapeHtml(String(row.message).slice(0, 120))}</td>`;
      tr.addEventListener("click", () => {
        window.alert(row.message || row.category);
      });
      body.appendChild(tr);
    }
  }

  const modules = {};
  for (const e of state.errors) {
    modules[e.agent] = (modules[e.agent] || 0) + 1;
  }
  if (errorChart) {
    errorChart.data.labels = Object.keys(modules);
    errorChart.data.datasets[0].data = Object.values(modules);
    errorChart.update("none");
  }

  const agents = ["all", ...new Set(state.errors.map((e) => e.agent))].filter(Boolean);
  const severities = ["all", "ERROR", "WARNING", "CRITICAL"];
  const chips = $("error-filters");
  chips.innerHTML = "";
  for (const a of agents) {
    const btn = document.createElement("button");
    btn.className = "chip" + (state.errorFilter.agent === a ? " active" : "");
    btn.textContent = a;
    btn.addEventListener("click", () => { state.errorFilter.agent = a; renderErrorTable(); });
    chips.appendChild(btn);
  }
  for (const s of severities) {
    const btn = document.createElement("button");
    btn.className = "chip" + (state.errorFilter.severity === s ? " active" : "");
    btn.textContent = s;
    btn.addEventListener("click", () => { state.errorFilter.severity = s; renderErrorTable(); });
    chips.appendChild(btn);
  }
}

async function refreshAgents() {
  try {
    const res = await fetch("/agents");
    const list = await res.json();
    state.agents = new Map(list.map((a) => [a.agent_id, a]));
    renderAgents();
  } catch {}
}

async function refreshApprovals() {
  try {
    const res = await fetch("/approvals?pending_only=true");
    const items = await res.json();
    renderApprovalPage(Array.isArray(items) ? items : []);
  } catch {}
}

function renderApprovalPage(items) {
  const container = $("approvals");
  $("approval-count").textContent = items.length;
  if (items.length === 0) {
    state.approvalPage = 0;
    container.innerHTML = '<div class="empty">No pending approvals.</div>';
    return;
  }
  if (state.approvalPage >= items.length) state.approvalPage = items.length - 1;
  if (state.approvalPage < 0) state.approvalPage = 0;
  const idx = state.approvalPage;
  const item = items[idx];
  const pageLabel = `${idx + 1} / ${items.length}`;
  container.innerHTML = `
    <div class="approval">
      <div class="meta">
        <div><b>${escapeHtml(item.step_name)}</b> — ${escapeHtml(item.agent_id)}</div>
        <div>${escapeHtml(item.summary || "")} ${item.confidence_score ? `(conf ${(item.confidence_score * 100).toFixed(0)}%)` : ""}</div>
      </div>
      <div class="actions">
        <button class="btn-approve" data-id="${item.approval_id}" data-ok="true">Approve</button>
        <button class="btn-reject" data-id="${item.approval_id}" data-ok="false">Reject</button>
      </div>
    </div>
    <div class="approval-pager">
      <button type="button" class="pager-btn" id="approval-prev" ${idx === 0 ? "disabled" : ""}>‹</button>
      <span class="pager-label">${pageLabel}</span>
      <button type="button" class="pager-btn" id="approval-next" ${idx >= items.length - 1 ? "disabled" : ""}>›</button>
    </div>`;
  container.querySelectorAll(".actions button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const resp = await fetch(`/approvals/${btn.dataset.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved: btn.dataset.ok === "true" }),
      });
      if (!resp.ok) {
        window.alert(`Approval failed (${resp.status})`);
        return;
      }
      refreshApprovals();
    });
  });
  $("approval-prev")?.addEventListener("click", () => {
    state.approvalPage -= 1;
    renderApprovalPage(items);
  });
  $("approval-next")?.addEventListener("click", () => {
    state.approvalPage += 1;
    renderApprovalPage(items);
  });
}

async function refreshErrors() {
  try {
    const fileRes = await fetch("/telemetry/errors");
    const summary = await fileRes.json();
    for (const inc of summary.recent_incidents || []) {
      upsertError(normalizeIncident(inc));
    }
  } catch {}
  try {
    const res = await fetch("/errors?limit=50");
    const list = await res.json();
    for (const event of list) {
      upsertError(normalizeIncident(event));
    }
  } catch {}
}

async function refreshAccuracy() {
  try {
    const res = await fetch("/telemetry/accuracy");
    const payload = await res.json();
    const audits = payload.audits || [];
    const body = $("quality-rows");
    body.innerHTML = "";
    if (audits.length === 0) {
      body.innerHTML = '<tr><td colspan="6" class="empty">No accuracy audits yet. Open Evidence Audit in the launcher.</td></tr>';
    } else {
      for (const a of [...audits].reverse()) {
        const human = isHumanReviewed(a);
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${escapeHtml(a.rfq_number || "")}</td>
          <td>${escapeHtml(a.customer || "")}</td>
          <td>${escapeHtml(a.ai_confidence_avg_pct ?? "")}%</td>
          <td>${human ? `${escapeHtml(a.overall_accuracy_pct)}%` : "pending"}</td>
          <td>${escapeHtml(a.accuracy_grade || "")}</td>
          <td>${escapeHtml(a.amended_cells_count ?? 0)}</td>`;
        body.appendChild(tr);
      }
    }

    const reviewed = audits.filter(isHumanReviewed);
    if (accuracyChart) {
      accuracyChart.data.labels = reviewed.map((a) => a.rfq_number || a.timestamp || "");
      accuracyChart.data.datasets[0].data = reviewed.map((a) => a.overall_accuracy_pct || 0);
      accuracyChart.update("none");
    }
  } catch {}
}

function handleEvent(event) {
  const isError = !!event.is_error;
  if (isError) {
    upsertError(normalizeIncident(event));
  }
  appendLog("logs", event, isError);

  const et = event.event_type;
  if (["AGENT_REGISTERED", "HEARTBEAT", "AGENT_OFFLINE"].includes(et)) {
    refreshAgents();
  }
  if (["APPROVAL_REQUESTED", "APPROVAL_DECIDED"].includes(et)) {
    refreshApprovals();
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/monitor`);
  ws.onopen = () => {
    $("conn-dot").className = "dot dot-up";
    $("conn-label").textContent = "live";
  };
  ws.onclose = () => {
    $("conn-dot").className = "dot dot-down";
    $("conn-label").textContent = "reconnecting...";
    setTimeout(connect, 1500);
  };
  ws.onmessage = (msg) => {
    try { handleEvent(JSON.parse(msg.data)); } catch {}
  };
}

initChart();
refreshAgents();
refreshApprovals();
refreshErrors();
refreshAccuracy();
connect();
setInterval(refreshAgents, 5000);
setInterval(refreshApprovals, 8000);
setInterval(refreshErrors, 8000);
setInterval(refreshAccuracy, 10000);
