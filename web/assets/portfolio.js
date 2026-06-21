/* Casefolio portfolio builder wizard */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { pid: null, selected: new Set() };
  const steps = ["step-context", "step-work", "step-interview", "step-avatar", "step-generate"];

  function show(i) {
    steps.forEach((id, n) => $(id).classList.toggle("hide", n !== i - 1));
    [...$("progress").children].forEach((d, n) => d.classList.toggle("on", n < i));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
      ...opts,
    });
    if (!res.ok) {
      const m = await res.json().catch(() => ({}));
      throw new Error(m.detail || `Request failed (${res.status})`);
    }
    return res.json();
  }
  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  api("/api/health").then((h) => { $("aiState").textContent = h.ai_enabled ? "AI: live" : "AI: offline (built-in mode)"; }).catch(() => {});

  // ---- Step 1 ----
  $("toWork").onclick = () => {
    if ($("context").value.trim().length < 12) { $("context").focus(); return; }
    loadCases(); show(2);
  };

  // ---- Step 2: work picker ----
  async function loadCases() {
    const box = $("caseList");
    try {
      const { cases } = await api("/api/case-studies");
      if (!cases.length) { box.innerHTML = `<span class="muted">No case studies yet — <a href="/builder">create one</a> or just add external links below.</span>`; return; }
      box.innerHTML = "";
      cases.forEach((c) => {
        const l = document.createElement("label");
        l.innerHTML = `<input type="checkbox" value="${esc(c.slug)}">
          <div class="ph">${c.thumbnail ? `<img src="${esc(c.thumbnail)}" alt="">` : "no image"}</div>
          <div class="t">${esc(c.title)}</div>`;
        const cb = l.querySelector("input");
        cb.onchange = () => {
          l.classList.toggle("on", cb.checked);
          cb.checked ? state.selected.add(c.slug) : state.selected.delete(c.slug);
          updateWorkInfo();
        };
        box.appendChild(l);
      });
    } catch (e) { box.innerHTML = `<span class="muted">Couldn't load case studies.</span>`; }
  }

  $("addExt").onclick = () => {
    const row = document.createElement("div");
    row.className = "ext-row";
    row.innerHTML = `<input class="txt" placeholder="Title">
      <input class="txt" placeholder="https://dribbble.com/...">
      <button class="linkbtn" title="remove">✕</button>`;
    row.querySelector("button").onclick = () => { row.remove(); updateWorkInfo(); };
    row.querySelectorAll("input").forEach((i) => i.oninput = updateWorkInfo);
    $("extList").appendChild(row);
  };

  function externals() {
    return [...document.querySelectorAll("#extList .ext-row")].map((r) => {
      const [title, url] = r.querySelectorAll("input");
      return { title: title.value.trim(), url: url.value.trim() };
    }).filter((e) => e.title && e.url);
  }
  function updateWorkInfo() {
    const n = state.selected.size + externals().length;
    $("workInfo").textContent = n ? `${n} project${n === 1 ? "" : "s"} selected` : "You can also build a portfolio with no projects yet.";
  }

  $("toInterview").onclick = async () => {
    const btn = $("toInterview");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Thinking…';
    try {
      const out = await api("/api/portfolios", {
        method: "POST",
        body: JSON.stringify({
          context: $("context").value.trim(),
          case_slugs: [...state.selected],
          external: externals(),
        }),
      });
      state.pid = out.id;
      renderQuestions(out);
    } catch (e) { alert(e.message); }
    finally { btn.disabled = false; btn.textContent = "Continue →"; }
  };

  // ---- Step 3: interview ----
  function renderQuestions(out) {
    if (out.ready || !(out.questions && out.questions.length)) { show(4); return; }
    const box = $("questions"); box.innerHTML = "";
    out.questions.forEach((q) => {
      const w = document.createElement("label");
      w.className = "fld";
      w.innerHTML = `<span class="q">${esc(q.question)}</span>` +
        (q.why ? `<span class="why">${esc(q.why)}</span>` : "") +
        `<textarea data-q="${esc(q.question)}" placeholder="${esc(q.placeholder || "")}"></textarea>`;
      box.appendChild(w);
    });
    $("roundInfo").textContent = out.note || "";
    show(3);
  }

  $("answersBtn").onclick = async () => {
    const answers = {};
    $("questions").querySelectorAll("textarea").forEach((t) => { if (t.value.trim()) answers[t.dataset.q] = t.value.trim(); });
    const btn = $("answersBtn");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Saving…';
    try { renderQuestions(await api(`/api/portfolios/${state.pid}/answers`, { method: "POST", body: JSON.stringify({ answers }) })); }
    catch (e) { alert(e.message); }
    finally { btn.disabled = false; btn.textContent = "Continue →"; }
  };

  // ---- Step 4: avatar ----
  const drop = $("drop"), fileInput = $("fileInput");
  drop.onclick = () => fileInput.click();
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files[0]); });
  fileInput.onchange = () => upload(fileInput.files[0]);

  async function upload(file) {
    if (!file || !file.type.startsWith("image/")) return;
    const fd = new FormData(); fd.append("file", file);
    try {
      const out = await api(`/api/portfolios/${state.pid}/assets`, { method: "POST", body: fd });
      $("thumbs").innerHTML = `<div class="thumb"><img src="${out.asset.url}" alt=""></div>`;
      $("avatarInfo").textContent = "Photo uploaded.";
    } catch (e) { alert(e.message); }
  }

  $("toGenerate").onclick = () => show(5);

  // ---- Step 5: generate ----
  $("generateBtn").onclick = async () => {
    const btn = $("generateBtn");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Generating…';
    $("genNote").classList.remove("hide");
    $("genNote").textContent = "Writing your portfolio and choosing a template…";
    try {
      const out = await api(`/api/portfolios/${state.pid}/generate`, { method: "POST" });
      window.location.href = `${out.url}?owner=${state.pid}`;
    } catch (e) {
      $("genNote").textContent = "Something went wrong: " + e.message;
      btn.disabled = false; btn.innerHTML = "✨ Generate portfolio";
    }
  };
})();
