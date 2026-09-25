const NAV_ITEMS = [
  ["overview", "Overview", "layout-dashboard"],
  ["guide", "Interview Guide", "list-checks"],
  ["insights", "Cross-Call Insights", "git-compare-arrows"],
  ["ask-all", "Ask All Calls", "messages-square"],
  ["ask-one", "Ask One Call", "message-square-lock"],
  ["transcripts", "Transcript Explorer", "file-search"],
  ["status", "Data Status", "database"],
  ["methodology", "Methodology", "workflow"],
];

const state = {
  view: "overview",
  transcripts: [],
  selectedTranscript: "FR",
  pendingCitation: null,
  credentials: {
    apiKey: sessionStorage.getItem("eci-gemini-key") || "",
    model: sessionStorage.getItem("eci-gemini-model") || "gemini-2.0-flash",
  },
};

const root = document.getElementById("view-root");
const desktopNav = document.getElementById("desktop-nav");
const mobileNav = document.getElementById("mobile-nav");
const toast = document.getElementById("toast");

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function icon(name, classes = "") {
  return `<i data-lucide="${name}" class="${classes}"></i>`;
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2800);
}

function loading(count = 4) {
  root.innerHTML = `
    <div class="view-header">
      <div><p class="eyebrow">Loading</p><h1>Preparing evidence</h1></div>
    </div>
    <div class="grid metrics-grid">
      ${Array.from({ length: count }, () => '<div class="skeleton"></div>').join("")}
    </div>
  `;
}

function errorView(error) {
  root.innerHTML = `
    <div class="view-header">
      <div><p class="eyebrow">Request failed</p><h1>Unable to load this view</h1></div>
    </div>
    <div class="error-card">${escapeHtml(error.message || String(error))}</div>
  `;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "The request failed.");
  return data;
}

function renderNav() {
  const markup = NAV_ITEMS.map(([id, label, iconName]) => `
    <button class="nav-button ${state.view === id ? "active" : ""}"
      data-view="${id}" type="button">
      ${icon(iconName)}
      <span>${label}</span>
    </button>
  `).join("");

  desktopNav.innerHTML = markup;
  mobileNav.innerHTML = `${markup}
    <button class="nav-button" id="mobile-settings" type="button">
      ${icon("sliders-horizontal")}<span>Gemini settings</span>
    </button>`;
  refreshIcons();
}

function header(eyebrow, title, description, actions = "") {
  return `
    <header class="view-header">
      <div>
        <p class="eyebrow">${escapeHtml(eyebrow)}</p>
        <h1>${escapeHtml(title)}</h1>
        <p>${escapeHtml(description)}</p>
      </div>
      ${actions ? `<div class="actions">${actions}</div>` : ""}
    </header>
  `;
}

function coverageBadge(value) {
  const label = {
    sufficient: "Sufficient evidence",
    partial: "Partial evidence",
    insufficient: "Insufficient evidence",
  }[value] || value;
  return `<span class="coverage-badge ${escapeHtml(value)}">${escapeHtml(label)}</span>`;
}

function citationChip(citation) {
  return `<button class="citation-chip" data-citation="${escapeHtml(citation.chunk_id)}"
    type="button">${escapeHtml(citation.chunk_id)}</button>`;
}

function evidenceCards(citations) {
  return citations.map(citation => `
    <article class="quote-card">
      <div class="chip-row">${citationChip(citation)}
        ${citation.incomplete_transcript
          ? '<span class="status-badge warning">Incomplete source</span>' : ""}
      </div>
      <blockquote>“${escapeHtml(citation.quote)}”</blockquote>
      <div class="quote-meta">
        ${escapeHtml(citation.market)} · ${escapeHtml(citation.expert_name)} ·
        ${escapeHtml(citation.expert_role)} · ${escapeHtml(citation.timestamp)}
      </div>
    </article>
  `).join("");
}

function setView(view) {
  state.view = view;
  window.location.hash = view;
  mobileNav.classList.remove("open");
  renderNav();
  renderCurrentView();
}

async function ensureTranscripts() {
  if (!state.transcripts.length) {
    state.transcripts = await api("/api/transcripts");
  }
  return state.transcripts;
}

async function renderOverview() {
  loading();
  const data = await api("/api/overview");
  const mode = state.credentials.apiKey
    ? `Browser Gemini override · ${state.credentials.model}`
    : data.gemini_configured
      ? `Server Gemini · ${data.gemini_model}`
      : "Local retrieval mode";

  root.innerHTML = `
    ${header(
      "Research dashboard",
      "European Robotic Surgery Market",
      "A source-grounded view of adoption, purchasing economics, training and evidence gaps.",
      `<button class="button secondary" data-view="guide">${icon("list-checks")}Explore the guide</button>
       <button class="button primary" data-view="ask-all">${icon("messages-square")}Ask across calls</button>`
    )}

    <section class="grid metrics-grid" aria-label="Research metrics">
      ${metric("Expert calls", data.calls, "France, Germany and UK", "phone-call")}
      ${metric("Evidence moments", data.expert_moments, "Timestamped expert answers", "quote")}
      ${metric("Source integrity", "Verified", data.source_integrity, "shield-check")}
      ${metric("Incomplete calls", data.incomplete_transcripts, "Germany and UK", "triangle-alert")}
    </section>

    <div class="section-heading">
      <h2>Evidence snapshots</h2>
      <p>Concise findings constrained to the supplied calls.</p>
    </div>

    <section class="grid snapshot-grid">
      ${data.snapshots.map((item, index) => `
        <article class="card">
          <span class="status-badge ${index === 3 ? "warning" : "neutral"}">
            ${index === 3 ? "Evidence gap" : "Source-grounded"}
          </span>
          <h3 style="margin-top:16px">${escapeHtml(item.title)}</h3>
          <p class="card-copy">${escapeHtml(item.text)}</p>
        </article>
      `).join("")}
      <article class="card">
        <h3>Generation mode</h3>
        <p class="card-copy">${escapeHtml(mode)}</p>
      </article>
    </section>

    <div class="section-heading">
      <h2>Market view</h2>
      <p>Qualitative comparison only; no external metrics are introduced.</p>
    </div>

    <section class="table-card">
      <table class="data-table">
        <thead><tr><th>Market</th><th>Adoption</th><th>Purchase emphasis</th><th>Timeline evidence</th></tr></thead>
        <tbody>
          ${data.markets_summary.map(row => `
            <tr>
              <td>${escapeHtml(row.market)}</td>
              <td>${escapeHtml(row.adoption)}</td>
              <td>${escapeHtml(row.focus)}</td>
              <td>${escapeHtml(row.timeline)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </section>
  `;
  refreshIcons();
}

function metric(label, value, note, iconName) {
  return `
    <article class="metric-card">
      <div class="metric-label"><span>${escapeHtml(label)}</span>${icon(iconName)}</div>
      <div class="metric-value">${escapeHtml(value)}</div>
      <div class="metric-note">${escapeHtml(note)}</div>
    </article>
  `;
}

async function renderGuide() {
  loading(3);
  const data = await api("/api/guide");
  root.innerHTML = `
    ${header(
      "Structured analysis",
      "Interview Guide",
      "Country-by-country answers with exact stored quotes and timestamp-linked citations."
    )}
    <section>
      ${data.questions.map(question => `
        <article class="card guide-question">
          <span class="question-number">QUESTION ${question.number}</span>
          <h2>${escapeHtml(question.question)}</h2>
          <div class="answer-grid">
            ${question.answers.map(answer => `
              <section class="answer-card">
                <div class="answer-card-header">
                  <h3>${escapeHtml(answer.market)}</h3>
                  ${coverageBadge(answer.coverage)}
                </div>
                <p class="answer-summary">${escapeHtml(answer.summary)}</p>
                ${answer.citations.length
                  ? evidenceCards(answer.citations)
                  : `<div class="quote-card">
                      ${icon("file-question")}
                      <p style="margin-top:10px">${escapeHtml(answer.summary)}</p>
                    </div>`}
                ${answer.citations.length
                  ? `<div class="source-actions">
                      <button class="button ghost" data-citation="${answer.citations[0].chunk_id}" type="button">
                        ${icon("external-link")}Open source
                      </button>
                    </div>`
                  : ""}
              </section>
            `).join("")}
          </div>
        </article>
      `).join("")}
    </section>
  `;
  refreshIcons();
}

async function renderInsights() {
  loading(4);
  const data = await api("/api/insights");
  root.innerHTML = `
    ${header(
      "Cross-call synthesis",
      "Shared themes and differences",
      "Deterministic insights mapped directly to exact source moments."
    )}
    <div class="insight-layout">
      ${insightColumn("Shared Themes", data.shared_themes)}
      ${insightColumn("Differences in Perspective", data.differences)}
    </div>
  `;
  refreshIcons();
}

function insightColumn(title, items) {
  return `
    <section>
      <div class="section-heading" style="margin-top:0">
        <h2>${escapeHtml(title)}</h2>
      </div>
      <div class="insight-stack">
        ${items.map(item => `
          <article class="card insight-card">
            <span class="status-badge neutral">${escapeHtml(item.category)}</span>
            <h3 style="margin-top:14px">${escapeHtml(item.title)}</h3>
            <p class="card-copy">${escapeHtml(item.explanation)}</p>
            <div class="chip-row" style="margin-top:14px">
              ${item.countries.map(country =>
                `<span class="country-chip">${escapeHtml(country)}</span>`
              ).join("")}
            </div>
            <div class="chip-row" style="margin-top:12px">
              ${item.citations.map(citationChip).join("")}
            </div>
            <details>
              <summary>Expand exact evidence</summary>
              <div class="insight-evidence">${evidenceCards(item.citations)}</div>
            </details>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function historyKey(scope) {
  return `eci-chat-${scope}`;
}

function loadHistory(scope) {
  try {
    return JSON.parse(localStorage.getItem(historyKey(scope)) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(scope, messages) {
  localStorage.setItem(historyKey(scope), JSON.stringify(messages.slice(-20)));
}

async function renderAskAll() {
  renderChatView({
    scope: "all",
    title: "Ask All Calls",
    description: "Search and answer across France, Germany and the United Kingdom.",
    endpoint: "/api/chat/all",
    suggestions: [
      "What prevents smaller hospitals from adopting robotic surgery?",
      "Why does surgeon training affect ROI?",
      "What do the experts agree on?",
      "How do France and the UK differ in purchasing decisions?",
      "How long does procurement take?",
    ],
  });
}

async function renderAskOne() {
  loading();
  const transcripts = await ensureTranscripts();
  const selected = transcripts.find(item => item.id === state.selectedTranscript) || transcripts[0];

  root.innerHTML = `
    ${header(
      "Focused research",
      "Ask One Call",
      "Restrict retrieval and generation to a single expert transcript."
    )}
    <div class="call-selector">
      <label>
        <span class="eyebrow" style="display:block;margin-bottom:6px">Selected transcript</span>
        <select id="call-select">
          ${transcripts.map(item => `
            <option value="${item.id}" ${item.id === selected.id ? "selected" : ""}>
              ${escapeHtml(item.market_name)} — ${escapeHtml(item.expert_name)}
            </option>
          `).join("")}
        </select>
      </label>
      <div id="call-preview" class="call-preview">
        <strong>${escapeHtml(selected.expert_name)}</strong> ·
        ${escapeHtml(selected.expert_role)} · ${escapeHtml(selected.market_name)}
      </div>
    </div>
    <div id="focused-chat"></div>
  `;

  document.getElementById("call-select").addEventListener("change", event => {
    state.selectedTranscript = event.target.value;
    renderAskOne();
  });

  renderChatView({
    scope: `transcript-${selected.id}`,
    title: "",
    description: "",
    endpoint: `/api/chat/transcript/${selected.id}`,
    target: document.getElementById("focused-chat"),
    banner: "This answer is restricted to the selected transcript.",
    suggestions: [
      "How is adoption changing?",
      "What is the main barrier?",
      "Why does training matter?",
      "How long does procurement take?",
    ],
    includeHeader: false,
  });
}

function renderChatView({
  scope,
  title,
  description,
  endpoint,
  suggestions,
  target = root,
  banner = "",
  includeHeader = true,
}) {
  const messages = loadHistory(scope);
  target.innerHTML = `
    ${includeHeader ? header("Grounded research chat", title, description) : ""}
    <section class="chat-shell">
      ${banner ? `<div class="chat-banner">${icon("lock-keyhole")}${escapeHtml(banner)}</div>` : ""}
      <div class="chat-toolbar">
        <p id="chat-mode">${state.credentials.apiKey
          ? `Browser Gemini override · ${escapeHtml(state.credentials.model)}`
          : "Server-configured mode"}</p>
        <button class="button ghost" id="clear-chat" type="button">
          ${icon("trash-2")}Clear history
        </button>
      </div>
      <div class="chat-history" id="chat-history"></div>
      <form class="chat-composer" id="chat-form">
        <div class="suggestions">
          ${suggestions.map(value =>
            `<button class="suggestion" type="button" data-suggestion="${escapeHtml(value)}">${escapeHtml(value)}</button>`
          ).join("")}
        </div>
        <label class="sr-only" for="chat-question">Research question</label>
        <div class="composer-row">
          <textarea id="chat-question" maxlength="1000"
            placeholder="Ask a question grounded in the supplied transcripts…"></textarea>
          <button class="button primary" type="submit">
            ${icon("arrow-up")}Send
          </button>
        </div>
      </form>
    </section>
  `;

  const historyElement = target.querySelector("#chat-history");
  renderMessages(historyElement, messages);

  target.querySelectorAll("[data-suggestion]").forEach(button => {
    button.addEventListener("click", () => {
      target.querySelector("#chat-question").value = button.dataset.suggestion;
      target.querySelector("#chat-question").focus();
    });
  });

  target.querySelector("#clear-chat").addEventListener("click", () => {
    localStorage.removeItem(historyKey(scope));
    renderMessages(historyElement, []);
  });

  target.querySelector("#chat-form").addEventListener("submit", async event => {
    event.preventDefault();
    const input = target.querySelector("#chat-question");
    const question = input.value.trim();
    if (!question) return;

    const updated = loadHistory(scope);
    updated.push({ role: "user", text: question });
    saveHistory(scope, updated);
    input.value = "";
    renderMessages(historyElement, updated, true);

    try {
      const response = await api(endpoint, {
        method: "POST",
        body: JSON.stringify({
          question,
          api_key: state.credentials.apiKey || null,
          model: state.credentials.model || null,
        }),
      });
      updated.push({ role: "assistant", ...response });
      saveHistory(scope, updated);
      renderMessages(historyElement, updated);
    } catch (error) {
      updated.push({
        role: "assistant",
        text: error.message,
        answer: error.message,
        coverage: "insufficient",
        limitations: [],
        evidence: [],
        retrieval_summary: "The request could not be completed.",
        generation_mode: "Error",
      });
      saveHistory(scope, updated);
      renderMessages(historyElement, updated);
    }
  });

  refreshIcons();
}

function renderMessages(container, messages, isLoading = false) {
  if (!messages.length && !isLoading) {
    container.innerHTML = `
      <div class="empty-chat">
        <div>
          ${icon("search-check")}
          <strong>Ask from the evidence</strong>
          <p>Answers remain constrained to the three supplied calls.</p>
        </div>
      </div>`;
    refreshIcons();
    return;
  }

  container.innerHTML = messages.map(message => {
    if (message.role === "user") {
      return `<article class="message user"><div class="message-bubble">${escapeHtml(message.text)}</div></article>`;
    }

    return `
      <article class="message assistant">
        <div class="message-bubble">
          <div class="answer-text">${escapeHtml(message.answer || message.text)}</div>
          <div class="message-meta">
            ${coverageBadge(message.coverage || "partial")}
            <span>${escapeHtml(message.generation_mode || "")}</span>
            <span>${escapeHtml(message.retrieval_summary || "")}</span>
          </div>
          <div class="actions">
            <button class="button ghost copy-answer" type="button" data-copy="${escapeHtml(message.answer || message.text)}">
              ${icon("copy")}Copy answer
            </button>
          </div>
          ${message.evidence?.length ? `
            <details class="evidence-panel">
              <summary>View ${message.evidence.length} supporting source moments</summary>
              <div class="insight-evidence">${evidenceCards(message.evidence)}</div>
            </details>` : ""}
        </div>
      </article>`;
  }).join("");

  if (isLoading) {
    container.insertAdjacentHTML("beforeend", `
      <article class="message assistant">
        <div class="message-bubble">
          <div class="skeleton" style="min-height:72px"></div>
        </div>
      </article>`);
  }

  container.querySelectorAll(".copy-answer").forEach(button => {
    button.addEventListener("click", () => {
      navigator.clipboard.writeText(button.dataset.copy);
      showToast("Answer copied");
    });
  });

  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

async function renderTranscripts() {
  loading();
  const transcripts = await ensureTranscripts();
  if (!transcripts.length) {
    root.innerHTML = `
      ${header("Source reader", "Transcript Explorer", "No transcripts are currently indexed.")}
      <div class="error-card">Run ingestion from Data Status before exploring transcripts.</div>`;
    return;
  }

  if (!transcripts.some(item => item.id === state.selectedTranscript)) {
    state.selectedTranscript = transcripts[0].id;
  }

  const detail = await api(`/api/transcripts/${state.selectedTranscript}`);
  root.innerHTML = `
    ${header(
      "Source reader",
      "Transcript Explorer",
      "Read exact source turns, search within a call, and open stable citation moments."
    )}
    <div class="explorer-layout">
      <aside class="transcript-tabs" aria-label="Transcript selection">
        ${transcripts.map(item => `
          <button class="transcript-tab ${item.id === detail.id ? "active" : ""}"
            data-transcript="${item.id}" type="button">
            <strong>${escapeHtml(item.market_name)}</strong>
            <span>${escapeHtml(item.expert_name)}</span>
          </button>
        `).join("")}
      </aside>
      <section class="transcript-reader">
        <header class="card transcript-header">
          <div class="transcript-header-row">
            <div>
              <p class="eyebrow">${escapeHtml(detail.market_name)}</p>
              <h2>${escapeHtml(detail.expert_name)}</h2>
              <p class="muted">${escapeHtml(detail.expert_role)}</p>
            </div>
            <span class="status-badge ${detail.is_incomplete ? "warning" : "success"}">
              ${detail.is_incomplete ? "Source ends mid-sentence" : "Complete supplied source"}
            </span>
          </div>
          <label class="transcript-search">
            <span class="sr-only">Search transcript</span>
            <input id="transcript-search" type="search" placeholder="Search this transcript…">
          </label>
        </header>
        <div class="turn-list" id="turn-list">
          ${detail.turns.map(turn => transcriptTurn(turn)).join("")}
        </div>
        ${detail.is_incomplete ? `
          <div class="incomplete-note">
            The supplied transcript deliberately ends mid-sentence. The missing continuation has not been inferred.
          </div>` : ""}
      </section>
    </div>
  `;

  root.querySelectorAll("[data-transcript]").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedTranscript = button.dataset.transcript;
      state.pendingCitation = null;
      renderTranscripts();
    });
  });

  const search = document.getElementById("transcript-search");
  search.addEventListener("input", () => {
    const query = search.value.toLowerCase().trim();
    root.querySelectorAll(".turn").forEach(turn => {
      turn.hidden = query && !turn.textContent.toLowerCase().includes(query);
    });
  });

  root.querySelectorAll("[data-copy-turn]").forEach(button => {
    button.addEventListener("click", () => {
      navigator.clipboard.writeText(button.dataset.copyTurn);
      showToast("Source text copied");
    });
  });

  root.querySelectorAll("[data-show-context]").forEach(button => {
    button.addEventListener("click", () => {
      const element = document.getElementById(`turn-${button.dataset.showContext}`);
      element?.previousElementSibling?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  refreshIcons();

  if (state.pendingCitation) {
    window.setTimeout(() => {
      const element = document.getElementById(`turn-${state.pendingCitation}`);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
        element.classList.add("highlight");
        window.setTimeout(() => element.classList.remove("highlight"), 3600);
      }
      state.pendingCitation = null;
    }, 80);
  }
}

function transcriptTurn(turn) {
  const id = turn.chunk_id ? `id="turn-${escapeHtml(turn.chunk_id)}"` : "";
  return `
    <article ${id} class="turn ${turn.is_expert_answer ? "expert" : "interviewer"}">
      <time class="turn-time">${escapeHtml(turn.timestamp)}</time>
      <div>
        <div class="turn-speaker">${escapeHtml(turn.speaker)}</div>
        <p class="turn-text">${escapeHtml(turn.text)}</p>
        ${turn.is_expert_answer ? `
          <div class="turn-actions">
            <button class="citation-chip" data-citation="${escapeHtml(turn.chunk_id)}" type="button">
              ${escapeHtml(turn.chunk_id)}
            </button>
            <button class="button ghost" data-copy-turn="${escapeHtml(turn.text)}" type="button">
              ${icon("copy")}Copy text
            </button>
            <button class="button ghost" data-show-context="${escapeHtml(turn.chunk_id)}" type="button">
              ${icon("history")}Show context
            </button>
          </div>` : ""}
      </div>
    </article>
  `;
}

async function openCitation(chunkId) {
  try {
    const citation = await api(`/api/evidence/${encodeURIComponent(chunkId)}`);
    state.selectedTranscript = citation.transcript_id;
    state.pendingCitation = citation.chunk_id;
    setView("transcripts");
  } catch (error) {
    showToast(error.message);
  }
}

async function renderStatus() {
  loading();
  const data = await api("/api/system/status");
  root.innerHTML = `
    ${header(
      "Operations",
      "Data Status",
      "Inspect local source storage, vector persistence, generation configuration and ingestion state.",
      `<button class="button primary" id="refresh-data" type="button">${icon("refresh-cw")}Refresh data</button>`
    )}
    <dl class="status-list">
      ${statusRow("Raw files detected", data.raw_files_detected)}
      ${statusRow("Valid raw files", data.valid_raw_files)}
      ${statusRow("Invalid raw files", data.invalid_raw_files)}
      ${statusRow("Calls parsed", data.calls_parsed)}
      ${statusRow("Expert chunks indexed", data.expert_chunks_indexed)}
      ${statusRow("Incomplete transcripts", data.incomplete_transcripts)}
      ${statusRow("SQLite", `${data.sqlite_status} · ${data.sqlite_path}`)}
      ${statusRow("ChromaDB", `${data.chroma_status} · ${data.chroma_path}`)}
      ${statusRow("Embedding model", data.embedding_model)}
      ${statusRow("Gemini", data.gemini_configured
        ? `Configured · ${data.gemini_model}`
        : "Not configured · local retrieval mode")}
      ${statusRow("Browser override", state.credentials.apiKey
        ? `Active · ${state.credentials.model}`
        : "Not configured")}
      ${statusRow("Last ingestion", data.last_ingestion_time || "No completed ingestion")}
      ${statusRow("Last startup action", data.last_ingestion_skipped ? "Skipped · corpus unchanged" : "Ingestion or refresh executed")}
      ${statusRow("Corpus fingerprint", data.raw_corpus_fingerprint || "Not available")}
    </dl>

    <div class="section-heading">
      <h2>Raw file validation</h2>
      <p>Every boot validates new transcript files before ingestion.</p>
    </div>
    <section class="table-card">
      <table class="data-table">
        <thead>
          <tr>
            <th>Filename</th>
            <th>Status</th>
            <th>Market</th>
            <th>Expert</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          ${data.raw_file_checks.map(item => `
            <tr>
              <td>${escapeHtml(item.filename)}</td>
              <td>${item.valid
                ? '<span class="status-badge success">Valid</span>'
                : '<span class="status-badge warning">Invalid</span>'}</td>
              <td>${escapeHtml(item.market_name || "—")}</td>
              <td>${escapeHtml(item.expert_name || "—")}</td>
              <td>${escapeHtml(item.reason || "Ready for ingestion")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </section>

    <div id="ingestion-result" style="margin-top:16px"></div>
  `;
  document.getElementById("refresh-data").addEventListener("click", async event => {
    const button = event.currentTarget;
    const result = document.getElementById("ingestion-result");
    button.disabled = true;
    button.innerHTML = `${icon("loader-circle")}Refreshing…`;
    result.innerHTML = '<div class="skeleton"></div>';
    refreshIcons();

    try {
      const response = await api("/api/ingest", { method: "POST" });
      state.transcripts = [];
      result.innerHTML = `
        <div class="card">
          <span class="status-badge ${response.skipped ? "neutral" : "success"}">
            ${response.skipped ? "Ingestion skipped" : "Ingestion completed"}
          </span>
          <p style="margin-top:12px">${escapeHtml(response.message)}</p>
          <p class="muted" style="margin-top:7px">
            ${response.files_discovered} discovered · ${response.valid_files} valid ·
            ${response.invalid_files} invalid · ${response.vector_records_synchronized} vectors synchronized
          </p>
        </div>`;
      showToast("Data synchronized");
    } catch (error) {
      result.innerHTML = `<div class="error-card">${escapeHtml(error.message)}</div>`;
    } finally {
      button.disabled = false;
      button.innerHTML = `${icon("refresh-cw")}Refresh data`;
      refreshIcons();
    }
  });

  refreshIcons();
}

function statusRow(term, value) {
  return `<div class="status-row"><dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

function renderMethodology() {
  const steps = [
    ["01", "Raw transcript files"],
    ["02", "Timestamp-aware parser"],
    ["03", "SQLite source store"],
    ["04", "Local embeddings"],
    ["05", "Persistent ChromaDB"],
    ["06", "Hybrid retrieval"],
    ["07", "Optional Gemini"],
    ["08", "Citation validation"],
  ];

  root.innerHTML = `
    ${header(
      "Technical methodology",
      "Grounding before generation",
      "A simple architecture designed to keep every important claim traceable to stored source evidence."
    )}
    <section class="pipeline">
      ${steps.map(([number, label]) => `
        <article class="pipeline-card">
          <span>${number}</span>
          <strong>${escapeHtml(label)}</strong>
        </article>
      `).join("")}
    </section>

    <section class="method-grid">
      ${methodCard("Timestamp-preserving chunks",
        "Expert answers remain aligned to their original timestamps. Interviewer questions are retained as retrieval context without becoming citation chunks.")}
      ${methodCard("Retrieval before generation",
        "The system narrows the evidence first. Gemini receives retrieved excerpts rather than unrestricted access to outside knowledge.")}
      ${methodCard("Quotes remain deterministic",
        "The language model never supplies final quote strings. The API resolves exact quote text and metadata from SQLite.")}
      ${methodCard("Server-side validation",
        "Every generated citation must belong to the retrieved set and resolve to an expert-answer source record.")}
      ${methodCard("Incomplete-source handling",
        "Germany and UK are marked incomplete. Their final source turns remain exactly truncated, and missing material is never completed.")}
      ${methodCard("Local retrieval mode",
        "Without Gemini, semantic and lexical retrieval still work and the interface presents deterministic stored evidence.")}
    </section>

    <div class="section-heading">
      <h2>Scale to 30+ calls</h2>
      <p>Preserve the grounding boundary while upgrading operations.</p>
    </div>
    <article class="card">
      <div class="chip-row">
        ${[
          "Async ingestion", "PostgreSQL", "pgvector or managed vectors",
          "Caching", "Reranking", "Evaluation sets", "Observability",
          "Authentication", "Workspaces", "Human review"
        ].map(item => `<span class="country-chip">${escapeHtml(item)}</span>`).join("")}
      </div>
    </article>
  `;
}

function methodCard(title, text) {
  return `<article class="card"><h3>${escapeHtml(title)}</h3><p class="card-copy">${escapeHtml(text)}</p></article>`;
}

async function renderCurrentView() {
  try {
    if (state.view === "overview") await renderOverview();
    else if (state.view === "guide") await renderGuide();
    else if (state.view === "insights") await renderInsights();
    else if (state.view === "ask-all") await renderAskAll();
    else if (state.view === "ask-one") await renderAskOne();
    else if (state.view === "transcripts") await renderTranscripts();
    else if (state.view === "status") await renderStatus();
    else if (state.view === "methodology") renderMethodology();
  } catch (error) {
    errorView(error);
  }
}

async function updateModeIndicator() {
  const indicator = document.getElementById("mode-indicator");
  if (state.credentials.apiKey) {
    indicator.textContent = `Browser Gemini override · ${state.credentials.model}`;
    return;
  }

  try {
    const status = await api("/api/system/status");
    indicator.textContent = status.gemini_configured
      ? `Gemini grounded generation · ${status.gemini_model}`
      : "Local retrieval mode — Gemini generation disabled";
  } catch {
    indicator.textContent = "System status unavailable";
  }
}

function setupSettings() {
  const dialog = document.getElementById("settings-dialog");
  const form = document.getElementById("settings-form");
  const keyInput = document.getElementById("gemini-key");
  const modelInput = document.getElementById("gemini-model");

  function openSettings() {
    keyInput.value = state.credentials.apiKey;
    modelInput.value = state.credentials.model;
    dialog.showModal();
  }

  document.getElementById("settings-button").addEventListener("click", openSettings);

  form.addEventListener("submit", event => {
    if (event.submitter?.value !== "save") return;
    event.preventDefault();
    state.credentials.apiKey = keyInput.value.trim();
    state.credentials.model = modelInput.value.trim() || "gemini-2.0-flash";
    sessionStorage.setItem("eci-gemini-key", state.credentials.apiKey);
    sessionStorage.setItem("eci-gemini-model", state.credentials.model);
    dialog.close();
    updateModeIndicator();
    showToast(state.credentials.apiKey
      ? "Browser Gemini override enabled"
      : "Using server configuration");
  });

  document.getElementById("clear-credentials").addEventListener("click", () => {
    state.credentials.apiKey = "";
    state.credentials.model = "gemini-2.0-flash";
    sessionStorage.removeItem("eci-gemini-key");
    sessionStorage.removeItem("eci-gemini-model");
    keyInput.value = "";
    modelInput.value = state.credentials.model;
    dialog.close();
    updateModeIndicator();
    showToast("Browser credential override cleared");
  });

  document.addEventListener("click", event => {
    if (event.target.closest("#mobile-settings")) openSettings();
  });
}

document.addEventListener("click", event => {
  const viewButton = event.target.closest("[data-view]");
  if (viewButton) setView(viewButton.dataset.view);

  const citationButton = event.target.closest("[data-citation]");
  if (citationButton && state.view !== "transcripts") {
    openCitation(citationButton.dataset.citation);
  }
});

document.getElementById("mobile-menu-button").addEventListener("click", () => {
  mobileNav.classList.toggle("open");
});

window.addEventListener("hashchange", () => {
  const requested = window.location.hash.replace("#", "");
  if (NAV_ITEMS.some(([id]) => id === requested) && requested !== state.view) {
    state.view = requested;
    renderNav();
    renderCurrentView();
  }
});

const initialView = window.location.hash.replace("#", "");
if (NAV_ITEMS.some(([id]) => id === initialView)) state.view = initialView;

renderNav();
setupSettings();
updateModeIndicator();
renderCurrentView();