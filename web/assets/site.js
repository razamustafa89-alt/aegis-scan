/* Casefolio — public portfolio renderer */
(() => {
  const root = document.getElementById("root");
  const tplLink = document.getElementById("tplLink");
  const slug = decodeURIComponent(location.pathname.replace(/^\/p\//, "").replace(/\/$/, ""));
  const ownerId = new URLSearchParams(location.search).get("owner");
  let assetUrls = {};
  let data = null;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const url = (ref) => assetUrls[ref] || ref || "";

  function applyTheme(theme) {
    if (!theme) return;
    const el = document.documentElement;
    if (theme.primary) el.style.setProperty("--t-primary", theme.primary);
    if (theme.accent) el.style.setProperty("--t-accent", theme.accent);
  }
  const setTemplate = (name) => { tplLink.href = `/assets/templates/${name}.css`; };
  const paras = (b) => String(b || "").split(/\n{2,}/).map((p) => `<p>${esc(p)}</p>`).join("");

  function links(list) {
    return (list || []).filter((l) => l.url).map((l) =>
      `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label || l.url)}</a>`).join("");
  }

  function renderBlock(b) {
    switch (b.type) {
      case "intro": {
        const av = b.avatar && url(b.avatar) ? `<img class="pf-avatar" src="${url(b.avatar)}" alt="${esc(b.name)}">` : "";
        return `<section class="pf-intro">${av}
          <div class="who">
            ${b.role ? `<div class="role">${esc(b.role)}</div>` : ""}
            <h1>${esc(b.name)}</h1>
            ${b.tagline ? `<p class="tagline">${esc(b.tagline)}</p>` : ""}
            ${b.location ? `<div class="loc">${esc(b.location)}</div>` : ""}
            ${(b.links && b.links.length) ? `<div class="pf-links">${links(b.links)}</div>` : ""}
          </div></section>`;
      }
      case "about":
        return `<section class="pf-section"><h2>${esc(b.heading || "About")}</h2>
          <div class="body">${paras(b.body)}</div></section>`;
      case "work": {
        const cards = (b.projects || []).map((p) => {
          const thumb = p.thumbnail ? `<div class="thumb"><img src="${esc(p.thumbnail)}" alt=""></div>` : "";
          const inner = `${thumb}<div class="meta"><h3>${esc(p.title)}</h3>
            ${p.blurb ? `<p>${esc(p.blurb)}</p>` : ""}
            ${p.href ? `<span class="go">View →</span>` : ""}</div>`;
          return p.href
            ? `<a class="pf-card" href="${esc(p.href)}">${inner}</a>`
            : `<div class="pf-card">${inner}</div>`;
        }).join("");
        if (!cards) return "";
        return `<section class="pf-section"><h2>${esc(b.heading || "Selected Work")}</h2>
          <div class="pf-work">${cards}</div></section>`;
      }
      case "skills": {
        const chips = (b.skills || []).map((s) => `<span>${esc(s)}</span>`).join("");
        if (!chips) return "";
        return `<section class="pf-section"><h2>${esc(b.heading || "Skills")}</h2>
          <div class="pf-skills">${chips}</div></section>`;
      }
      case "testimonials": {
        const qs = (b.quotes || []).map((q) =>
          `<div class="pf-quote"><p>“${esc(q.text)}”</p>${q.attribution ? `<cite>— ${esc(q.attribution)}</cite>` : ""}</div>`).join("");
        if (!qs) return "";
        return `<section class="pf-section"><h2>${esc(b.heading || "What people say")}</h2>
          <div class="pf-quotes">${qs}</div></section>`;
      }
      case "contact": {
        const mailto = b.email
          ? `<a class="pf-btn" href="mailto:${esc(b.email)}" style="text-decoration:none">${esc(b.cta || "Email me")}</a>` : "";
        return `<section class="pf-section"><div class="pf-contact">
          <h2>${esc(b.heading || "Get in touch")}</h2>
          ${b.body ? `<div class="body">${esc(b.body)}</div>` : ""}
          ${(b.links && b.links.length) ? `<div class="pf-links" style="margin-bottom:18px">${links(b.links)}</div>` : ""}
          <form class="pf-form" id="contactForm">
            <input name="name" placeholder="Your name" autocomplete="name">
            <input name="email" type="email" placeholder="Your email" autocomplete="email">
            <textarea name="body" placeholder="Your message" required></textarea>
            <button class="pf-btn" type="submit">Send message</button>
            <div class="pf-msg" id="contactMsg">${mailto ? "Or " + mailto : ""}</div>
          </form></div></section>`;
      }
      default:
        return "";
    }
  }

  function wireContact() {
    const form = document.getElementById("contactForm");
    if (!form) return;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button");
      const out = document.getElementById("contactMsg");
      const payload = {
        name: form.name.value.trim(), email: form.email.value.trim(), body: form.body.value.trim(),
      };
      if (!payload.body) return;
      btn.disabled = true; btn.textContent = "Sending…";
      try {
        const res = await fetch(`/api/portfolio/${encodeURIComponent(slug)}/contact`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error();
        form.reset();
        out.textContent = "Thanks — your message was sent.";
        btn.textContent = "Sent ✓";
      } catch (_) {
        out.textContent = "Couldn't send right now. Please try the email link.";
        btn.disabled = false; btn.textContent = "Send message";
      }
    });
  }

  function ownerControls(meta) {
    if (!ownerId) return;
    const bar = document.createElement("div");
    bar.className = "cs-controls";
    const opts = (meta.templates || []).map((t) =>
      `<option value="${t}" ${t === meta.template ? "selected" : ""}>${t}</option>`).join("");
    const theme = data.theme || {};
    bar.innerHTML = `<span>Template</span><select id="tplSel">${opts}</select>
      <span>Brand</span>
      <input type="color" id="cPrimary" value="${theme.primary || "#2c2c2c"}" title="Primary">
      <input type="color" id="cAccent" value="${theme.accent || "#ff5a5f"}" title="Accent">
      <button id="copyLink">Copy share link</button>
      <button class="x" id="hideBar">✕</button>`;
    document.body.appendChild(bar);
    const patch = (payload) => fetch(`/api/portfolios/${ownerId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    bar.querySelector("#tplSel").onchange = (e) => { setTemplate(e.target.value); patch({ template: e.target.value }); };
    const onColor = () => {
      const t = { ...(data.theme || {}),
        primary: bar.querySelector("#cPrimary").value, accent: bar.querySelector("#cAccent").value };
      data.theme = t; applyTheme(t); patch({ theme: t });
    };
    bar.querySelector("#cPrimary").oninput = onColor;
    bar.querySelector("#cAccent").oninput = onColor;
    bar.querySelector("#copyLink").onclick = (e) => {
      navigator.clipboard.writeText(location.origin + "/p/" + meta.slug); e.target.textContent = "Copied!";
    };
    bar.querySelector("#hideBar").onclick = () => bar.remove();
  }

  async function load() {
    try {
      const res = await fetch(`/api/portfolio/${encodeURIComponent(slug)}`);
      if (!res.ok) throw new Error();
      const meta = await res.json();
      data = meta;
      if (!meta.document) throw new Error();
      assetUrls = meta.document.asset_urls || {};
      setTemplate(meta.template || "editorial");
      applyTheme(meta.theme);
      const doc = meta.document;
      document.title = `${doc.title} · Portfolio`;
      document.getElementById("metaDesc").content = doc.summary || "";
      root.innerHTML = (doc.blocks || []).map(renderBlock).join("") +
        `<div class="pf-foot"><span>${esc(doc.title)}</span>
          <span>Built with <a href="/">Casefolio</a></span></div>`;
      wireContact();
      ownerControls(meta);
    } catch (_) {
      root.innerHTML = `<p style="padding:80px 0;color:#888">This portfolio isn't available.</p>`;
    }
  }
  load();
})();
