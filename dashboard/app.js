/* Cerberus dashboard — polls FastAPI every 1s */

const $ = (id) => document.getElementById(id);
let lastSeen = 0;

const chart = new Chart($("chart"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "seen",
        data: [],
        borderColor: "#3ecf8e",
        backgroundColor: "rgba(62,207,142,0.12)",
        tension: 0.3,
        fill: true,
        pointRadius: 0,
      },
      {
        label: "dropped",
        data: [],
        borderColor: "#e85d5d",
        tension: 0.3,
        pointRadius: 0,
      },
    ],
  },
  options: {
    responsive: true,
    animation: false,
    scales: {
      x: { ticks: { color: "#8aa094", maxTicksLimit: 8 }, grid: { color: "rgba(62,207,142,0.08)" } },
      y: { beginAtZero: true, ticks: { color: "#8aa094" }, grid: { color: "rgba(62,207,142,0.08)" } },
    },
    plugins: { legend: { labels: { color: "#8aa094" } } },
  },
});

function badge(text, cls) {
  return `<span class="badge ${cls}">${text}</span>`;
}

async function jget(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function jpost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) {
    let detail = await r.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch (_) {
      /* keep */
    }
    throw new Error(detail);
  }
  return r.json();
}

function toast(msg, ok = true) {
  const el = $("toast");
  el.hidden = false;
  el.className = `toast ${ok ? "ok" : "err"}`;
  el.textContent = msg;
  clearTimeout(el._t);
  el._t = setTimeout(() => {
    el.hidden = true;
  }, 4000);
}

async function runAction(label, fn) {
  try {
    const res = await fn();
    const note = res && res.note ? ` — ${res.note}` : "";
    toast(`${label}: OK${note}`, true);
    await refresh();
  } catch (err) {
    console.error(err);
    toast(`${label}: ${err.message || err}`, false);
  }
}

function setKernelEnabled(live) {
  ["btn-thr", "btn-clear", "btn-adaptive-on", "btn-adaptive-off", "thr-input"].forEach((id) => {
    $(id).disabled = !live;
  });
  $("panel-controls").classList.toggle("dimmed", !live);
  $("controls-hint").textContent = live
    ? "Live XDP attached — changes write into the kernel BPF map."
    : "Disabled until XDP is attached. On Ubuntu: sudo python3 backend/serve.py <iface>";
}

async function refresh() {
  try {
    const [status, top, events, series] = await Promise.all([
      jget("/api/status"),
      jget("/api/top?limit=12"),
      jget("/api/events?limit=25"),
      jget("/api/timeseries?limit=60"),
    ]);

    const live = !!status.xdp_live || !!status.attached;
    const preview = !!status.ui_preview;
    const attack = !!status.attack_running;
    const flash = !!status.flashcrowd_running;
    setKernelEnabled(live);

    const t = status.totals || {};
    const seen = t.seen ?? 0;
    $("m-seen").textContent = seen;
    $("m-dropped").textContent = t.dropped ?? 0;
    $("m-passed").textContent = t.passed ?? 0;
    $("m-thr").textContent = status.threshold ?? "—";
    if (!$("thr-input").matches(":focus")) {
      $("thr-input").value = status.threshold ?? 250;
    }

    $("m-seen-sub").textContent = preview ? "UI preview (not XDP)" : live ? "live XDP" : "no data yet";
    $("m-dropped-sub").textContent = preview ? "preview drops" : "XDP_DROP";

    document.querySelectorAll(".metrics article").forEach((el) => el.classList.remove("hot"));
    if (seen > lastSeen) {
      $("metrics").querySelector("article")?.classList.add("hot");
    }
    lastSeen = seen;

    // Mode banner
    const banner = $("mode-banner");
    banner.hidden = false;
    banner.className = `mode-banner${live ? " live" : ""}`;
    banner.innerHTML = status.help_message
      ? status.help_message.replace(
          /sudo python3 backend\/serve\.py <iface>/g,
          "<code>sudo python3 backend/serve.py &lt;iface&gt;</code>"
        )
      : "";

    // Activity strip
    const act = $("activity");
    if (attack || flash) {
      act.hidden = false;
      act.className = `activity${flash && !attack ? " flash" : ""}`;
      const what = attack ? "ATTACK generator running" : "FLASH CROWD generator running";
      const extra = preview ? " · UI preview counters ticking" : live ? " · live XDP counting" : "";
      act.innerHTML = `<span class="dot"></span><span>${what}${extra}</span>`;
    } else {
      act.hidden = true;
    }

    const adaptiveOn = !!(status.adaptive && status.adaptive.enabled);
    $("badges").innerHTML = [
      badge(live ? "Tier-1 ON" : "Tier-1 OFF", live ? "on" : "off"),
      badge(adaptiveOn ? "Adaptive ON" : "Adaptive OFF", adaptiveOn ? "on" : "warn"),
      badge(status.ml_available ? "ML ready" : "ML pending", status.ml_available ? "on" : "off"),
      badge(status.atlas_connected ? "Atlas ON" : "Atlas OFF", status.atlas_connected ? "on" : "off"),
      badge(preview ? "UI PREVIEW" : live ? "LIVE" : "API ONLY", preview ? "warn" : live ? "on" : "off"),
      badge(attack ? "ATTACK" : flash ? "FLASH" : "idle", attack ? "danger" : flash ? "on" : "off"),
    ].join("");

    $("chart-chip").textContent = preview ? "ui preview" : live ? "live" : "idle";
    $("chart-chip").className = `chip${preview || live ? " on" : ""}`;
    $("top-chip").textContent = top.source || "—";
    $("top-chip").className = `chip${top.source === "ui_preview" ? " warn" : top.source === "xdp" ? " on" : ""}`;
    $("events-chip").textContent = `${(events.events || []).length} events`;

    const rows = top.top || [];
    $("top-body").innerHTML = rows
      .map((r) => {
        const ip = r.ip || r.src_ip;
        const action = r.action || "pass";
        return `<tr><td>${ip}</td><td>${r.count}</td><td class="action-${action}">${action}</td></tr>`;
      })
      .join("") || `<tr><td colspan="3">No sources yet — start an attack to see activity</td></tr>`;

    $("events").innerHTML = (events.events || [])
      .map((e) => {
        const when = e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : "";
        return `<li><span class="t">${e.type}</span>${e.src_ip || ""} ${e.detail || ""}<em>${when}</em></li>`;
      })
      .join("") || "<li>No events yet</li>";

    const points = series.points || [];
    chart.data.labels = points.map((p) => new Date((p.ts || 0) * 1000).toLocaleTimeString());
    chart.data.datasets[0].data = points.map((p) => p.total_pkts);
    chart.data.datasets[1].data = points.map((p) => p.dropped);
    chart.update();

    $("iface").textContent = `iface ${status.device || "—"}`;
    $("mode").textContent = `mode ${status.mode_label || status.mode || "—"}`;
    $("footer-note").textContent = preview ? "UI preview active" : live ? "live XDP" : "poll 1s";
  } catch (err) {
    console.error(err);
    $("mode-banner").hidden = false;
    $("mode-banner").className = "mode-banner";
    $("mode-banner").textContent = "Cannot reach API — is the server running on :8080?";
  }
}

function demoBody() {
  return {
    target: $("target").value || "127.0.0.1",
    rate: Number($("rate").value) || 200,
    duration: 60,
  };
}

$("btn-thr").onclick = () =>
  runAction("Set threshold", () => jpost("/api/threshold", { threshold: Number($("thr-input").value) }));
$("btn-clear").onclick = () => runAction("Clear", () => jpost("/api/clear", {}));
$("btn-adaptive-on").onclick = () =>
  runAction("Adaptive ON", () => jpost("/api/adaptive", { enabled: true }));
$("btn-adaptive-off").onclick = () =>
  runAction("Adaptive OFF", () => jpost("/api/adaptive", { enabled: false }));
$("btn-attack").onclick = () =>
  runAction("Start attack", () => jpost("/api/demo/attack/start", demoBody()));
$("btn-attack-stop").onclick = () =>
  runAction("Stop attack", () => jpost("/api/demo/attack/stop", {}));
$("btn-flash").onclick = () =>
  runAction("Start flash crowd", () => jpost("/api/demo/flashcrowd/start", demoBody()));
$("btn-flash-stop").onclick = () =>
  runAction("Stop flash", () => jpost("/api/demo/flashcrowd/stop", {}));

refresh();
setInterval(refresh, 1000);

/* Command console — a browser version of cli/ddosctl.py */

const consoleOut = $("console-output");
const consoleIn = $("console-input");
const consoleHistory = [];
let consoleHistoryPos = -1;

function printLine(html) {
  const line = document.createElement("div");
  line.innerHTML = html;
  consoleOut.appendChild(line);
  consoleOut.scrollTop = consoleOut.scrollHeight;
}

function fmtTs(ts) {
  return ts ? new Date(ts * 1000).toLocaleString() : "-";
}

const HELP_TEXT =
  "commands: status | top [n] | events [n] | attack | threshold &lt;n&gt; | clear | help | cls";

async function runConsoleCommand(raw) {
  const text = raw.trim();
  if (!text) return;
  printLine(`<span class="c-cmd">${text}</span>`);
  consoleHistory.push(text);
  consoleHistoryPos = consoleHistory.length;

  const [cmd, ...rest] = text.split(/\s+/);

  try {
    switch (cmd) {
      case "help":
        printLine(`<span class="c-muted">${HELP_TEXT}</span>`);
        break;

      case "cls":
        consoleOut.innerHTML = "";
        break;

      case "status": {
        const s = await jget("/api/status");
        const t = s.totals || {};
        printLine(
          `<span class="c-muted">threshold=${s.threshold} adaptive=${
            s.adaptive && s.adaptive.enabled ? "on" : "off"
          } seen=${t.seen ?? 0} dropped=${t.dropped ?? 0} passed=${t.passed ?? 0}</span>`
        );
        break;
      }

      case "top": {
        const limit = Number(rest[0]) || 12;
        const data = await jget(`/api/top?limit=${limit}`);
        const rows = data.top || [];
        if (!rows.length) {
          printLine('<span class="c-muted">(no traffic recorded yet)</span>');
          break;
        }
        rows.forEach((r) => {
          const ip = r.ip || r.src_ip;
          const action = r.action || "pass";
          const cls = action === "drop" ? "c-bad" : "c-ok";
          printLine(`<span class="c-muted">${ip}  count=${r.count}  action=</span><span class="${cls}">${action}</span>`);
        });
        break;
      }

      case "events": {
        const limit = Number(rest[0]) || 15;
        const data = await jget(`/api/events?limit=${limit}`);
        const rows = data.events || [];
        if (!rows.length) {
          printLine('<span class="c-muted">(no events recorded yet)</span>');
          break;
        }
        rows.forEach((e) => {
          printLine(
            `<span class="c-muted">${fmtTs(e.ts)}  ${e.type}  ${e.src_ip || "-"}  ${e.detail || ""}</span>`
          );
        });
        break;
      }

      case "attack": {
        const [series, top] = await Promise.all([
          jget("/api/timeseries?limit=10"),
          jget("/api/top?limit=30"),
        ]);
        const points = series.points || [];
        if (points.length < 2) {
          printLine('<span class="c-muted">Not enough data yet to judge.</span>');
          break;
        }
        const first = points[0];
        const last = points[points.length - 1];
        const dTotal = (last.total_pkts ?? 0) - (first.total_pkts ?? 0);
        const dDropped = (last.dropped ?? 0) - (first.dropped ?? 0);
        const dropRate = dTotal > 0 ? (dDropped / dTotal) * 100 : 0;
        const blocked = (top.top || []).filter((r) => r.action === "drop");
        const isAttack = dropRate >= 5 || blocked.length > 0;
        if (isAttack) {
          printLine('<span class="c-bad">[!] ATTACK LIKELY</span>');
        } else {
          printLine('<span class="c-ok">[OK] No attack detected</span>');
        }
        printLine(
          `<span class="c-muted">recent drop rate: ${dropRate.toFixed(1)}% (last ${points.length} samples)</span>`
        );
        blocked.forEach((r) => {
          const ip = r.ip || r.src_ip;
          printLine(`<span class="c-bad">  ${ip}  count=${r.count}</span>`);
        });
        break;
      }

      case "threshold": {
        const value = Number(rest[0]);
        if (!value) {
          printLine('<span class="c-bad">usage: threshold &lt;number&gt;</span>');
          break;
        }
        const res = await jpost("/api/threshold", { threshold: value });
        printLine(`<span class="c-ok">OK</span><span class="c-muted"> ${JSON.stringify(res)}</span>`);
        await refresh();
        break;
      }

      case "clear": {
        const res = await jpost("/api/clear", {});
        printLine(`<span class="c-ok">OK</span><span class="c-muted"> ${JSON.stringify(res)}</span>`);
        await refresh();
        break;
      }

      default:
        printLine(`<span class="c-bad">unknown command: ${cmd}</span> — ${HELP_TEXT}`);
    }
  } catch (err) {
    printLine(`<span class="c-bad">error: ${err.message || err}</span>`);
  }
}

printLine('<span class="c-muted">Cerberus command console — type "help" to see commands.</span>');

consoleIn.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") {
    const val = consoleIn.value;
    consoleIn.value = "";
    runConsoleCommand(val);
  } else if (ev.key === "ArrowUp") {
    if (consoleHistoryPos > 0) {
      consoleHistoryPos -= 1;
      consoleIn.value = consoleHistory[consoleHistoryPos];
    }
    ev.preventDefault();
  } else if (ev.key === "ArrowDown") {
    if (consoleHistoryPos < consoleHistory.length - 1) {
      consoleHistoryPos += 1;
      consoleIn.value = consoleHistory[consoleHistoryPos];
    } else {
      consoleHistoryPos = consoleHistory.length;
      consoleIn.value = "";
    }
    ev.preventDefault();
  }
});
