/* Casefolio builder wizard */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { caseId: null, step: 1, questions: [], uploads: 0 };

  const steps = ["step-context", "step-interview", "step-upload", "step-generate"];
  function show(step) {
    state.step = step;
    steps.forEach((id, i) => $(id).classList.toggle("hide", i !== step - 1));
    [...$("progress").children].forEach((d, i) => d.classList.toggle("on", i < step));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
      ...opts,
    });
    if (!res.ok) {
      const msg = await res.json().catch(() => ({}));
      throw new Error(msg.detail || `Request failed (${res.status})`);
    }
    return res.json();
  }

  // Health badge
  api("/api/health").then((h) => {
    $("aiState").textContent = h.ai_enabled ? "AI: live" : "AI: offline (built-in mode)";
  }).catch(() => {});

  // ---- Step 1: context ----
  $("startBtn").onclick = async () => {
    const context = $("context").value.trim();
    if (context.length < 12) { $("context").focus(); return; }
    const btn = $("startBtn");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Thinking…';
    try {
      const out = await api("/api/case-studies", { method: "POST", body: JSON.stringify({ context }) });
      state.caseId = out.id;
      renderQuestions(out);
    } catch (e) { alert(e.message); }
    finally { btn.disabled = false; btn.textContent = "Continue →"; }
  };

  // ---- Step 2: interview ----
  function renderQuestions(out) {
    if (out.ready || !(out.questions && out.questions.length)) { show(3); return; }
    state.questions = out.questions;
    const box = $("questions");
    box.innerHTML = "";
    out.questions.forEach((q) => {
      const wrap = document.createElement("label");
      wrap.className = "fld";
      wrap.innerHTML = `<span class="q">${esc(q.question)}</span>` +
        (q.why ? `<span class="why">${esc(q.why)}</span>` : "") +
        `<textarea data-q="${esc(q.question)}" placeholder="${esc(q.placeholder || "")}"></textarea>`;
      box.appendChild(wrap);
    });
    $("roundInfo").textContent = out.note || "";
    show(2);
  }

  $("answersBtn").onclick = async () => {
    const answers = {};
    $("questions").querySelectorAll("textarea").forEach((t) => {
      if (t.value.trim()) answers[t.dataset.q] = t.value.trim();
    });
    const btn = $("answersBtn");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Saving…';
    try {
      const out = await api(`/api/case-studies/${state.caseId}/answers`,
        { method: "POST", body: JSON.stringify({ answers }) });
      renderQuestions(out);
    } catch (e) { alert(e.message); }
    finally { btn.disabled = false; btn.textContent = "Continue →"; }
  };

  // ---- Step 3: uploads ----
  const drop = $("drop"), fileInput = $("fileInput");
  drop.onclick = () => fileInput.click();
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault(); drop.classList.remove("over");
    handleFiles(e.dataTransfer.files);
  });
  fileInput.onchange = () => handleFiles(fileInput.files);

  async function handleFiles(files) {
    for (const file of files) {
      if (!file.type.startsWith("image/")) continue;
      const fd = new FormData();
      fd.append("file", file);
      try {
        const out = await api(`/api/case-studies/${state.caseId}/assets`, { method: "POST", body: fd });
        addThumb(out.asset.url);
        state.uploads = out.count;
        $("uploadInfo").textContent = `${state.uploads} image${state.uploads === 1 ? "" : "s"} uploaded.`;
      } catch (e) { alert(`${file.name}: ${e.message}`); }
    }
  }
  function addThumb(url) {
    const d = document.createElement("div");
    d.className = "thumb";
    d.innerHTML = `<img src="${url}" alt="">`;
    $("thumbs").appendChild(d);
  }

  $("toGenerate").onclick = () => show(4);

  // ---- Step 4: generate ----
  $("generateBtn").onclick = async () => {
    const btn = $("generateBtn");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Generating…';
    $("genNote").classList.remove("hide");
    $("genNote").textContent = "Writing your story, building diagrams and charts, and theming the page…";
    try {
      const out = await api(`/api/case-studies/${state.caseId}/generate`, { method: "POST" });
      window.location.href = `${out.url}?owner=${state.caseId}`;
    } catch (e) {
      $("genNote").textContent = "Something went wrong: " + e.message;
      btn.disabled = false; btn.innerHTML = "✨ Generate case study";
    }
  };

  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
})();
