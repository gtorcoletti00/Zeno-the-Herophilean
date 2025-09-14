// app.js — structural sidebar, theme toggle, bilingual layout
async function loadBodyJson() {
  if (typeof window.__BODY__ === "object" && window.__BODY__ !== null) return window.__BODY__;
  const res = await fetch("./body.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch body.json: ${res.statusText}`);
  return await res.json();
}

function sanitizeId(n) {
  return String(n || "").replace(/[^a-zA-Z0-9.\-_]+/g, "_").replace(/^_+|_+$/g, "");
}

/* THEME TOGGLE */
function initThemeToggle() {
  const btn = document.getElementById("themeToggle");
  const root = document.documentElement;
  const apply = (mode) => {
    if (mode === "dark") root.setAttribute("data-theme", "dark");
    else if (mode === "light") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
  };
  const saved = localStorage.getItem("theme");
  apply(saved || null);
  btn?.addEventListener("click", () => {
    const now = root.getAttribute("data-theme");
    const next = now === "dark" ? "light" : "dark";
    apply(next);
    localStorage.setItem("theme", next);
  });
}

/* Build a single row with two columns (Greek left, English right) */
function buildDivContent(d) {
  const tmp = document.createElement("div");
  tmp.innerHTML = d.html || "";
  const gr = Array.from(tmp.querySelectorAll('p[lang="grc"]'));
  const en = Array.from(tmp.querySelectorAll('p[lang="en"]'));

  if (en.length === 0) {
    const plain = document.createElement("div");
    plain.className = "div-html sec-main";
    plain.innerHTML = d.html || "";
    return plain;
  }

  const grid = document.createElement("div");
  grid.className = "div-html bilingual sec-main";

  const row = document.createElement("div");
  row.className = "bi-row bi-two";
  const left = document.createElement("div"); left.className = "bi-col bi-left";
  const right = document.createElement("div"); right.className = "bi-col bi-right";

  gr.forEach(p => left.appendChild(p));
  en.forEach(p => right.appendChild(p));

  row.appendChild(left); row.appendChild(right);
  grid.appendChild(row);
  return grid;
}

/* RENDER EVERYTHING */
function render(payload) {
  const titleEl = document.getElementById("work-title");
  const authorEl = document.getElementById("work-author");
  const tocEl = document.getElementById("toc");
  const mainEl = document.getElementById("edition");

  if (payload.meta?.title) titleEl.textContent = payload.meta.title;
  if (payload.meta?.author) authorEl.textContent = payload.meta.author;

  /* TOC */
  tocEl.innerHTML = "";
  const links = [];
  payload.divs.forEach((d) => {
    const id = "div_" + sanitizeId(d.n || d.type || "");
    const a = document.createElement("a");
    a.href = `#${id}`;
    a.textContent = d.n ? d.n : (d.type || "div");
    tocEl.appendChild(a);
    links.push([id, a]);
  });

  /* BODY */
  mainEl.innerHTML = "";
  payload.divs.forEach((d) => {
    const id = "div_" + sanitizeId(d.n || d.type || "");
    const sec = document.createElement("section");
    sec.id = id;

    const head = document.createElement("div");
    head.className = "sec-head";
    const h = document.createElement("h3");
    h.className = "sec-title";
    h.textContent = d.n ? `${d.n}${d.type ? " — " + d.type : ""}` : (d.type || "");
    head.appendChild(h);

    const hasCommentary = !!(d.commentaryHtml && d.commentaryHtml.trim());
    const hasApparatus  = !!(d.apparatusHtml && d.apparatusHtml.trim());
    if (hasCommentary || hasApparatus) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-toggle";
      btn.setAttribute("aria-expanded", "false");
      btn.textContent = "Mostra commentario e apparato";
      btn.addEventListener("click", () => toggleSection(sec, btn));
      head.appendChild(btn);
    }
    sec.appendChild(head);

    const wrapper = buildDivContent(d);
    sec.appendChild(wrapper);

    if (hasCommentary) {
      const aside = document.createElement("aside");
      aside.className = "sec-aside commentary";
      aside.innerHTML = `<h4 class="sec-minihead">Commentary</h4>${d.commentaryHtml}`;
      sec.appendChild(aside);
    }
    if (hasApparatus) {
      const app = document.createElement("div");
      app.className = "sec-apparatus";
      app.innerHTML = `<h4 class="sec-minihead">Apparatus criticus</h4>${d.apparatusHtml}`;
      sec.appendChild(app);
    }

    mainEl.appendChild(sec);
  });

  initSpanTitles();
  initActiveTOC(links);
  renderSpecimen(payload);
  initThemeToggle();
}

/* Sidebar specimen (witness sigla) */
function renderSpecimen(payload) {
  const sidebar = document.getElementById("specimenSidebar");
  if (!sidebar) return;

  let host = document.getElementById("specimen");
  if (!host) {
    host = document.createElement("div");
    host.id = "specimen";
    sidebar.appendChild(host);
  }

  const wits = (payload.meta && Array.isArray(payload.meta.witnesses) && payload.meta.witnesses.length)
    ? payload.meta.witnesses
    : [
        {id: "A",  text: "Codex A (fict.), saec. XII"},
        {id: "B",  text: "Codex B (fict.), saec. XIII"},
        {id: "C",  text: "Codex C (fict.), saec. XIV"},
        {id: "AI", text: "Aulus Intellex (ed.)"}
      ];

  if (!wits.length) { host.innerHTML = ""; return; }

  host.innerHTML = `
    <div class="specimen-card">
      <div class="specimen-head">SIGLA</div>
      <dl class="specimen-list">
        ${wits.map(w => `
          <div class="sig">
            <dt class="sigla">${w.id === "AI" ? "AI (ed.)" : w.id}</dt>
            <dd class="expansion">${w.text || ""}</dd>
          </div>`).join("")}
      </dl>
    </div>`;
}

function toggleSection(sec, btn) {
  const expanded = sec.classList.toggle("expanded");
  if (btn) {
    btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    btn.textContent = expanded ? "Nascondi commentario e apparato" : "Mostra commentario e apparato";
  }
}

function initSpanTitles() {
  const sel = '.div-html span.term, .div-html span.persName, .div-html span.rs, .div-html span.seg';
  document.querySelectorAll(sel).forEach(el => {
    if (!el.title) {
      const ds = el.dataset || {};
      const bits = [];
      if (ds.type) bits.push(`type=${ds.type}`);
      if (ds.key) bits.push(`key=${ds.key}`);
      if (ds.ref) bits.push(`ref=${ds.ref}`);
      if (ds.ana) bits.push(`ana=${ds.ana}`);
      if (ds.ident) bits.push(`ident=${ds.ident}`);
      const info = bits.join(" · ");
      if (info) el.title = info;
    }
  });
}

function initActiveTOC(links) {
  const byId = new Map(links);
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      const link = byId.get(e.target.id);
      if (link) {
        if (e.isIntersecting) {
          document.querySelectorAll(".toc a.active").forEach(a => a.classList.remove("active"));
          link.classList.add("active");
        }
      }
    });
  }, { rootMargin: "0px 0px -60% 0px", threshold: 0.1 });

  links.forEach(([id]) => {
    const sec = document.getElementById(id);
    if (sec) observer.observe(sec);
  });
}

(async () => {
  try {
    const data = await loadBodyJson();
    render(data);
  } catch (err) {
    document.getElementById("edition").innerHTML =
      `<p style="color:#b00"><strong>Error:</strong> ${String(err.message || err)}</p>
       <p>Tip: run <code>python -m http.server</code> in this folder and open <a href="http://localhost:8000/" target="_blank" rel="noopener">http://localhost:8000/</a>.</p>`;
    console.error(err);
  }
})();
