/* Casefolio — public case-study renderer */
(() => {
  const root = document.getElementById("root");
  const tplLink = document.getElementById("tplLink");
  const slug = decodeURIComponent(location.pathname.replace(/^\/case\//, "").replace(/\/$/, ""));
  const ownerId = new URLSearchParams(location.search).get("owner");

  let assetUrls = {};
  let data = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  const url = (ref) => assetUrls[ref] || "";

  function applyTheme(theme) {
    if (!theme) return;
    const el = document.documentElement;
    if (theme.primary) el.style.setProperty("--t-primary", theme.primary);
    if (theme.accent) el.style.setProperty("--t-accent", theme.accent);
  }

  function setTemplate(name) {
    tplLink.href = `/assets/templates/${name}.css`;
  }

  // ---- block renderers ----
  function paragraphs(body) {
    return String(body || "").split(/\n{2,}/).map((p) => `<p>${esc(p).replace(/\n/g, "<br>")}</p>`).join("");
  }

  function renderBlock(b) {
    switch (b.type) {
      case "hero": {
        const img = b.image && url(b.image)
          ? `<div class="cs-hero-img"><img src="${url(b.image)}" alt=""></div>` : "";
        const tags = (b.tags || []).map((t) => `<span class="cs-tag">${esc(t)}</span>`).join("");
        return `<section class="cs-hero">
          ${b.eyebrow ? `<div class="eyebrow">${esc(b.eyebrow)}</div>` : ""}
          <h1>${esc(b.title)}</h1>
          ${b.subtitle ? `<p class="impact">${esc(b.subtitle)}</p>` : ""}
          ${tags ? `<div class="cs-tags">${tags}</div>` : ""}
          ${img}
        </section>`;
      }
      case "meta": {
        const items = (b.items || []).filter((i) => i.value).map((i) =>
          `<div class="cs-meta-item"><div class="label">${esc(i.label)}</div><div class="value">${esc(i.value)}</div></div>`).join("");
        return items ? `<div class="cs-meta">${items}</div>` : "";
      }
      case "text":
        return `<section class="cs-section">
          ${b.heading ? `<h2>${esc(b.heading)}</h2>` : ""}
          <div class="body">${paragraphs(b.body)}</div></section>`;
      case "gallery": {
        const figs = (b.images || []).filter((i) => url(i.ref)).map((i) =>
          `<figure class="cs-fig"><img src="${url(i.ref)}" alt="${esc(i.caption)}">
            ${i.caption ? `<figcaption>${esc(i.caption)}</figcaption>` : ""}</figure>`).join("");
        if (!figs) return "";
        return `<section class="cs-section">${b.heading ? `<h2>${esc(b.heading)}</h2>` : ""}
          <div class="cs-gallery">${figs}</div></section>`;
      }
      case "flow-diagram":
        return `<section class="cs-section">${b.heading ? `<h2>${esc(b.heading)}</h2>` : ""}
          <figure class="cs-diagram"><pre class="mermaid">${esc(b.mermaid)}</pre>
          ${b.caption ? `<figcaption>${esc(b.caption)}</figcaption>` : ""}</figure></section>`;
      case "chart":
        return `<section class="cs-section">${b.heading ? `<h2>${esc(b.heading)}</h2>` : ""}
          <div class="cs-chart"><div class="holder"><canvas></canvas></div></div></section>`;
      case "metrics": {
        const items = (b.items || []).map((i) =>
          `<div class="cs-metric"><div class="num">${esc(i.value)}</div><div class="label">${esc(i.label)}</div></div>`).join("");
        return `<section class="cs-section">${b.heading ? `<h2>${esc(b.heading)}</h2>` : ""}
          <div class="cs-metrics">${items}</div></section>`;
      }
      case "quote":
        return `<section class="cs-quote"><blockquote>“${esc(b.text)}”</blockquote>
          ${b.attribution ? `<cite>— ${esc(b.attribution)}</cite>` : ""}</section>`;
      default:
        return "";
    }
  }

  function accent() {
    return getComputedStyle(document.documentElement).getPropertyValue("--t-accent").trim() || "#ff5a5f";
  }
  function textColor() {
    return getComputedStyle(document.documentElement).getPropertyValue("--t-muted").trim() || "#888";
  }

  function drawCharts(blocks) {
    const canvases = root.querySelectorAll(".cs-chart canvas");
    let ci = 0;
    blocks.filter((b) => b.type === "chart").forEach((b) => {
      const cv = canvases[ci++];
      if (!cv || !window.Chart) return;
      const palette = [accent(), "#7C8BFF", "#3DF59B", "#FFC24B", "#38E1FF"];
      new Chart(cv.getContext("2d"), {
        type: b.chart_type || "bar",
        data: {
          labels: b.labels || [],
          datasets: (b.datasets || []).map((d, i) => ({
            label: d.label || "",
            data: d.data || [],
            backgroundColor: (b.chart_type === "line") ? "transparent" : palette[i % palette.length],
            borderColor: palette[i % palette.length],
            borderWidth: 2,
            tension: 0.35,
          })),
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { labels: { color: textColor() } } },
          scales: (b.chart_type === "doughnut") ? {} : {
            x: { ticks: { color: textColor() }, grid: { display: false } },
            y: { ticks: { color: textColor() }, grid: { color: "rgba(128,128,128,.15)" } },
          },
        },
      });
    });
  }

  function renderDiagrams() {
    if (!window.mermaid) return;
    try {
      window.mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });
      window.mermaid.run({ nodes: root.querySelectorAll(".mermaid") });
    } catch (e) { /* leave source visible on failure */ }
  }

  function ownerControls(meta) {
    if (!ownerId) return;
    const bar = document.createElement("div");
    bar.className = "cs-controls";
    const opts = (meta.templates || []).map((t) =>
      `<option value="${t}" ${t === meta.template ? "selected" : ""}>${t}</option>`).join("");
    const theme = data.theme || {};
    bar.innerHTML = `
      <span>Template</span>
      <select id="tplSel">${opts}</select>
      <span>Brand</span>
      <input type="color" id="cPrimary" value="${theme.primary || "#2c2c2c"}" title="Primary">
      <input type="color" id="cAccent" value="${theme.accent || "#ff5a5f"}" title="Accent">
      <button id="copyLink">Copy share link</button>
      <button class="x" id="hideBar" title="Hide controls">✕</button>`;
    document.body.appendChild(bar);

    const patch = (payload) => fetch(`/api/case-studies/${ownerId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });

    bar.querySelector("#tplSel").onchange = (e) => { setTemplate(e.target.value); patch({ template: e.target.value }); };
    const onColor = () => {
      const t = { ...(data.theme || {}),
        primary: bar.querySelector("#cPrimary").value,
        accent: bar.querySelector("#cAccent").value };
      data.theme = t; applyTheme(t); patch({ theme: t });
    };
    bar.querySelector("#cPrimary").oninput = onColor;
    bar.querySelector("#cAccent").oninput = onColor;
    bar.querySelector("#copyLink").onclick = () => {
      navigator.clipboard.writeText(location.origin + "/case/" + meta.slug);
      bar.querySelector("#copyLink").textContent = "Copied!";
    };
    bar.querySelector("#hideBar").onclick = () => bar.remove();
  }

  async function load() {
    try {
      const res = await fetch(`/api/case/${encodeURIComponent(slug)}`);
      if (!res.ok) throw new Error("not found");
      const meta = await res.json();
      data = meta;
      if (!meta.document) throw new Error("not generated");
      assetUrls = meta.document.asset_urls || {};
      setTemplate(meta.template || "editorial");
      applyTheme(meta.theme);

      const doc = meta.document;
      document.title = `${doc.title} · Casefolio`;
      document.getElementById("metaDesc").content = doc.summary || "";

      const blocks = doc.blocks || [];
      root.innerHTML = blocks.map(renderBlock).join("") +
        `<div class="cs-foot"><span>${esc(doc.title)}</span>
          <span>Built with <a href="/">Casefolio</a></span></div>`;

      drawCharts(blocks);
      renderDiagrams();
      ownerControls(meta);
    } catch (e) {
      root.innerHTML = `<p style="padding:80px 0;color:#888">This case study isn't available.</p>`;
    }
  }

  load();
})();
