/**
 * Cogscope Drift Tracker — client-side charts (Chart.js).
 * Expects window.TRACKER_DATA and window.TRACKER_META from data.js.
 */
(function () {
  const ACCENT = "#4ade80";
  const ACCENT_DIM = "rgba(74, 222, 128, 0.35)";
  const GRID = "rgba(42, 53, 64, 0.8)";
  const TICK = "#9aa8b5";
  const SAMPLE_COLOR = "#fbbf24";

  const data = window.TRACKER_DATA || {};
  const meta = window.TRACKER_META || {};
  const models = meta.models || Object.keys(data);
  const annotations = meta.annotations || [];

  let active = models[0] || null;
  const charts = [];

  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1a2229",
        titleColor: "#e8edf2",
        bodyColor: "#9aa8b5",
        borderColor: "#2a3540",
        borderWidth: 1,
        titleFont: { family: "ui-monospace, monospace", size: 11 },
        bodyFont: { family: "ui-monospace, monospace", size: 11 },
      },
    },
    scales: {
      x: {
        type: "time",
        time: { unit: "day", tooltipFormat: "yyyy-MM-dd" },
        grid: { color: GRID },
        ticks: { color: TICK, font: { family: "ui-monospace, monospace", size: 10 } },
      },
    },
  };

  function destroyCharts() {
    while (charts.length) {
      const c = charts.pop();
      if (c) c.destroy();
    }
  }

  function makeChart(canvasId, label, field, yOpts) {
    const recs = data[active] || [];
    const ctx = document.getElementById(canvasId);
    if (!ctx || !recs.length) return null;

    const points = recs.map((r) => ({ x: r.timestamp, y: r[field] }));
    const isSample = recs.some((r) => r.sample);

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [
          {
            label,
            data: points,
            borderColor: ACCENT,
            backgroundColor: ACCENT_DIM,
            pointBackgroundColor: isSample ? SAMPLE_COLOR : ACCENT,
            pointBorderColor: isSample ? SAMPLE_COLOR : ACCENT,
            pointRadius: 5,
            pointHoverRadius: 7,
            borderWidth: 2,
            tension: 0.15,
            fill: false,
          },
        ],
      },
      options: {
        ...chartDefaults,
        plugins: {
          ...chartDefaults.plugins,
        },
        scales: {
          ...chartDefaults.scales,
          y: {
            ...yOpts,
            grid: { color: GRID },
            ticks: { color: TICK, font: { family: "ui-monospace, monospace", size: 10 } },
          },
        },
      },
    });
    charts.push(chart);
    return chart;
  }

  function renderCharts() {
    destroyCharts();
    const recs = data[active] || [];
    const badge = document.getElementById("model-badge");
    const title = document.getElementById("active-model-label");

    if (title) title.textContent = active || "—";
    if (badge) {
      const hasSample = recs.some((r) => r.sample);
      badge.textContent = hasSample ? "sample data" : "community data";
      badge.className = "badge " + (hasSample ? "badge--sample" : "badge--live");
    }

    if (!recs.length) return;

    makeChart("chart-depth", "Depth", "depth", {
      min: 0,
      title: { display: true, text: "steps", color: TICK, font: { size: 10 } },
    });
    makeChart("chart-verification", "Verification", "verification_steps", {
      min: 0,
      title: { display: true, text: "count", color: TICK, font: { size: 10 } },
    });
    makeChart("chart-hedging", "Hedging ratio", "hedging_ratio", {
      min: 0,
      max: 1,
      title: { display: true, text: "0–1", color: TICK, font: { size: 10 } },
    });
    makeChart("chart-drift", "Drift score", "drift_score", {
      min: 0,
      max: 1,
      title: { display: true, text: "0–1", color: TICK, font: { size: 10 } },
    });
  }

  function renderTabs() {
    const tabs = document.getElementById("model-tabs");
    if (!tabs) return;
    tabs.innerHTML = models
      .map(
        (m) =>
          `<button type="button" class="tab${m === active ? " active" : ""}" data-model="${m}" aria-pressed="${m === active}">${m}</button>`
      )
      .join("");
    tabs.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        active = btn.dataset.model;
        renderTabs();
        renderCharts();
      });
    });
  }

  function initAnnotations() {
    const section = document.getElementById("annotations-section");
    const list = document.getElementById("annotation-list");
    if (!section || !list) return;

    if (!annotations.length) {
      section.classList.add("hidden");
      return;
    }

    section.classList.remove("hidden");
    list.innerHTML = annotations
      .map(
        (a) =>
          `<li><strong>${a.date}</strong> — ${a.label}` +
          (a.source_url ? ` <a href="${a.source_url}" rel="noopener">source</a>` : "") +
          "</li>"
      )
      .join("");
  }

  renderTabs();
  renderCharts();
  initAnnotations();

  window.addEventListener("resize", () => {
    charts.forEach((c) => c.resize());
  });
})();
