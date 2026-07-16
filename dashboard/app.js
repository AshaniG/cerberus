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
