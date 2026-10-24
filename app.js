/**
 * Intelligent Candidate Discovery & Ranking System - Frontend Application
 * Fully integrated with PostgreSQL & SQLite Database Layer
 */

const API_BASE = "";

// Application State
let state = {
  activeTab: "leaderboard",
  candidates: [],
  totalCandidates: 0,
  page: 1,
  pageSize: 20,
  totalPages: 1,
  search: "",
  titleFilter: "",
  countryFilter: "",
  expFilter: "0-100",
  topOnly: true,
  starredOnly: false,
  stats: null,
  config: null,
  honeypots: [],
  shortlists: [],
  runs: [],
  dbStatus: null,
  selectedCandidate: null
};

// DOM Initialization
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  await fetchDbStatus();
  await fetchStats();
  await fetchConfig();
  await fetchCandidates();
  await fetchHoneypots();
  await fetchShortlists();
}

// ============================================================================
// API Calls
// ============================================================================

async function fetchDbStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/db/status`);
    const data = await res.json();
    state.dbStatus = data;
    renderDbStatus(data);
  } catch (err) {
    console.error("Error fetching DB status:", err);
  }
}

async function fetchStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    const data = await res.json();
    state.stats = data;
    renderStats(data);
    renderMetricsTab(data);
  } catch (err) {
    console.error("Error fetching stats:", err);
  }
}

async function fetchConfig() {
  try {
    const res = await fetch(`${API_BASE}/api/config`);
    const data = await res.json();
    state.config = data;
    renderConfigStudio(data);
  } catch (err) {
    console.error("Error fetching config:", err);
  }
}

async function fetchCandidates() {
  const [minExp, maxExp] = state.expFilter.split("-").map(Number);
  
  const params = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
    search: state.search,
    title: state.titleFilter,
    country: state.countryFilter,
    min_exp: minExp || 0,
    max_exp: maxExp || 100,
    top_only: state.topOnly ? "true" : "false",
    starred_only: state.starredOnly ? "true" : "false"
  });

  try {
    const res = await fetch(`${API_BASE}/api/candidates?${params.toString()}`);
    const data = await res.json();
    state.candidates = data.candidates || [];
    state.totalCandidates = data.total || 0;
    state.totalPages = data.total_pages || 1;
    renderCandidatesTable();
  } catch (err) {
    console.error("Error fetching candidates:", err);
  }
}

async function fetchHoneypots() {
  try {
    const res = await fetch(`${API_BASE}/api/honeypots`);
    const data = await res.json();
    state.honeypots = data.candidates || [];
    renderHoneypotsTable(state.honeypots);
    
    const badge = document.getElementById("nav-hp-badge");
    if (badge) badge.innerText = data.count || 0;
  } catch (err) {
    console.error("Error fetching honeypots:", err);
  }
}

async function fetchShortlists() {
  try {
    const res = await fetch(`${API_BASE}/api/shortlists`);
    const data = await res.json();
    state.shortlists = data.shortlists || [];
    renderShortlistsTable(state.shortlists);

    const badge = document.getElementById("nav-shortlist-badge");
    if (badge) badge.innerText = data.count || 0;
  } catch (err) {
    console.error("Error fetching shortlists:", err);
  }
}

async function fetchRuns() {
  try {
    const res = await fetch(`${API_BASE}/api/runs`);
    const data = await res.json();
    state.runs = data.runs || [];
    renderRunsTable(state.runs);
  } catch (err) {
    console.error("Error fetching runs:", err);
  }
}

async function fetchCandidateById(candidateId) {
  try {
    const res = await fetch(`${API_BASE}/api/candidates/${candidateId}`);
    return await res.json();
  } catch (err) {
    console.error(`Error fetching candidate ${candidateId}:`, err);
    return null;
  }
}

async function toggleCandidateStar(event, candidateId) {
  event.stopPropagation();
  const current = state.candidates.find(c => c.candidate_id === candidateId);
  const nextStarred = current ? !current.is_starred : true;

  try {
    const res = await fetch(`${API_BASE}/api/candidates/${candidateId}/shortlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred: nextStarred })
    });
    if (res.ok) {
      if (current) current.is_starred = nextStarred;
      renderCandidatesTable();
      await fetchShortlists();
      showToast(nextStarred ? "⭐ Candidate shortlisted & saved to DB" : "Removed star bookmark");
    }
  } catch (err) {
    showToast("❌ Error saving shortlist: " + err.message);
  }
}

async function saveModalShortlist() {
  if (!state.selectedCandidate) return;
  const candidateId = state.selectedCandidate.candidate_id;
  const statusSelect = document.getElementById("modal-shortlist-status");
  const notesInput = document.getElementById("modal-recruiter-notes");
  const isStarred = state.selectedCandidate.is_starred !== false;

  const payload = {
    status: statusSelect.value,
    recruiter_notes: notesInput.value,
    starred: isStarred
  };

  try {
    const res = await fetch(`${API_BASE}/api/candidates/${candidateId}/shortlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast("💾 Recruiter evaluation saved to database!");
      await fetchShortlists();
      await fetchCandidates();
    }
  } catch (err) {
    showToast("❌ Error saving evaluation: " + err.message);
  }
}

function toggleModalStar() {
  if (!state.selectedCandidate) return;
  state.selectedCandidate.is_starred = !state.selectedCandidate.is_starred;
  const btn = document.getElementById("modal-star-btn");
  if (btn) {
    btn.classList.toggle("active", state.selectedCandidate.is_starred);
  }
}

async function activateRun(runId) {
  try {
    const res = await fetch(`${API_BASE}/api/runs/${runId}/activate`, { method: "POST" });
    if (res.ok) {
      showToast(`⚡ Switched to Run: ${runId}`);
      await initApp();
      await fetchRuns();
    }
  } catch (err) {
    showToast("❌ Error activating run: " + err.message);
  }
}

async function saveConfigAndRerank() {
  const btn = document.getElementById("rerun-btn");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Scoring Engine Running...";
  }

  const updatedConfig = {
    CORE_FIT_WEIGHT: parseFloat(document.getElementById("slider-CORE_FIT_WEIGHT").value),
    TEXT_RELEVANCE_WEIGHT: parseFloat(document.getElementById("slider-TEXT_RELEVANCE_WEIGHT").value),
    TITLE_WEIGHT: parseFloat(document.getElementById("slider-TITLE_WEIGHT").value),
    SKILLS_WEIGHT: parseFloat(document.getElementById("slider-SKILLS_WEIGHT").value),
    CAREER_WEIGHT: parseFloat(document.getElementById("slider-CAREER_WEIGHT").value),
    EXPERIENCE_WEIGHT: parseFloat(document.getElementById("slider-EXPERIENCE_WEIGHT").value),
    LOCATION_WEIGHT: parseFloat(document.getElementById("slider-LOCATION_WEIGHT").value),
    EDUCATION_WEIGHT: parseFloat(document.getElementById("slider-EDUCATION_WEIGHT").value),
    JD_QUERY: document.getElementById("jd-query-input").value
  };

  try {
    const res = await fetch(`${API_BASE}/api/rank`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updatedConfig)
    });
    const result = await res.json();
    showToast("✅ Scoring pipeline completed! Leaderboard & DB updated.");
    await initApp();
  } catch (err) {
    showToast("❌ Failed to re-run pipeline: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🔄 Re-Run Scoring";
    }
  }
}

function reRunPipeline() {
  saveConfigAndRerank();
}

function exportSubmissionCSV() {
  window.location.href = `${API_BASE}/api/export`;
}

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (e) => {
    const text = e.target.result;
    let payload = null;

    try {
      if (file.name.endsWith(".json")) {
        payload = JSON.parse(text);
      } else {
        const lines = text.trim().split("\n");
        payload = lines.map(line => {
          const trimmed = line.trim();
          return trimmed ? JSON.parse(trimmed) : null;
        }).filter(Boolean);
      }
    } catch (err) {
      showToast("❌ Invalid JSON / JSONL file format!");
      return;
    }

    showToast("⏳ Ingesting & persisting to database...");

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`✅ ${data.message}`);
        await initApp();
      } else {
        showToast(`❌ Upload error: ${data.error}`);
      }
    } catch (err) {
      showToast(`❌ Network error uploading dataset: ${err.message}`);
    }
  };

  reader.readAsText(file);
}

// ============================================================================
// UI Render Functions
// ============================================================================

function renderDbStatus(status) {
  if (!status) return;
  const pill = document.getElementById("db-status-pill");
  const label = document.getElementById("db-engine-label");
  const badge = document.getElementById("db-details-badge");

  const isPg = status.engine === "postgresql";
  if (pill) {
    pill.className = `db-pill ${isPg ? '' : 'sqlite'}`;
  }
  if (label) {
    label.innerText = isPg ? "DB: PostgreSQL (Cloud)" : "DB: SQLite (Embedded)";
  }
  if (badge) {
    badge.className = `badge-tag ${isPg ? 'badge-emerald' : 'badge-indigo'}`;
    badge.innerText = `Engine: ${status.engine_display} (${status.total_candidates} candidates)`;
  }
}

function renderStats(stats) {
  if (!stats) return;
  document.getElementById("kpi-total").innerText = stats.total_candidates.toLocaleString();
  document.getElementById("kpi-valid-sub").innerText = `${stats.valid_candidates.toLocaleString()} Valid Profiles`;
  document.getElementById("kpi-honeypots").innerText = stats.honeypots_count;
  document.getElementById("kpi-top-score").innerText = stats.top_score.toFixed(4);
  document.getElementById("kpi-cutoff-score").innerText = stats.cutoff_score_100.toFixed(4);
  document.getElementById("kpi-avg-score").innerText = `Avg Top100: ${stats.avg_top100_score.toFixed(4)}`;
}

function renderCandidatesTable() {
  const tbody = document.getElementById("candidate-table-body");
  if (!tbody) return;

  if (state.candidates.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No candidates found matching the selected filters.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = state.candidates.map(c => {
    const s = c.scores || {};
    const rankClass = c.rank <= 3 ? "rank-top3" : (c.rank <= 10 ? "rank-top10" : "rank-normal");
    const rankLabel = c.rank > 0 ? `#${c.rank}` : "DISQ";
    const starActive = c.is_starred ? "active" : "";

    return `
      <tr>
        <td style="text-align: center;">
          <button class="btn-star ${starActive}" onclick="toggleCandidateStar(event, '${c.candidate_id}')" title="Star candidate">
            ⭐
          </button>
        </td>
        <td>
          <span class="rank-badge ${c.is_honeypot ? 'rank-honeypot' : rankClass}">
            ${rankLabel}
          </span>
        </td>
        <td>
          <div class="candidate-profile">
            <span class="candidate-name">${escapeHtml(c.name)}</span>
            <span class="candidate-title-company">${escapeHtml(c.title)} @ <strong>${escapeHtml(c.company)}</strong></span>
          </div>
        </td>
        <td>
          <span style="font-size: 0.8125rem; color: var(--text-main);">${escapeHtml(c.location)}, ${escapeHtml(c.country)}</span>
        </td>
        <td>
          <span class="badge-tag badge-indigo">${c.years_of_experience} yrs</span>
        </td>
        <td>
          <div style="display: flex; gap: 0.375rem; flex-wrap: wrap;">
            <span class="badge-tag badge-indigo" title="Core Fit">Core: ${s.core_fit ? s.core_fit.toFixed(2) : '--'}</span>
            <span class="badge-tag badge-amber" title="TF-IDF Relevance">Text: ${s.text_relevance ? s.text_relevance.toFixed(2) : '--'}</span>
            <span class="badge-tag badge-emerald" title="Behavioral Multiplier">${s.behavioral ? s.behavioral.toFixed(2) + 'x' : '--'}</span>
          </div>
        </td>
        <td>
          <div class="score-bar-wrapper">
            <div class="score-num">${s.final ? s.final.toFixed(4) : '0.0000'}</div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${Math.min((s.final / 1.2) * 100, 100)}%;"></div>
            </div>
          </div>
        </td>
        <td style="text-align: right;">
          <button class="btn btn-secondary" onclick="openCandidateModal('${c.candidate_id}')" style="padding: 0.375rem 0.75rem; font-size: 0.75rem;">
            Inspect 🔍
          </button>
        </td>
      </tr>
    `;
  }).join("");

  // Update pagination info
  const start = state.totalCandidates === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
  const end = Math.min(state.page * state.pageSize, state.totalCandidates);
  document.getElementById("pagination-info").innerText = `Showing ${start}-${end} of ${state.totalCandidates} candidates`;
  document.getElementById("page-num-display").innerText = `Page ${state.page} of ${state.totalPages}`;

  document.getElementById("prev-page-btn").disabled = state.page <= 1;
  document.getElementById("next-page-btn").disabled = state.page >= state.totalPages;
}

function renderShortlistsTable(shortlists) {
  const tbody = document.getElementById("shortlist-table-body");
  if (!tbody) return;

  if (shortlists.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No candidates shortlisted yet. Click the ⭐ star on any candidate in the Leaderboard to shortlist!
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = shortlists.map(sh => {
    let statusBadge = `<span class="badge-tag badge-indigo">Shortlisted</span>`;
    if (sh.status === "interviewing") statusBadge = `<span class="badge-tag badge-amber">📞 Interviewing</span>`;
    if (sh.status === "offer") statusBadge = `<span class="badge-tag badge-emerald">🎉 Offer Extended</span>`;
    if (sh.status === "rejected") statusBadge = `<span class="badge-tag badge-rose">Disqualified</span>`;

    return `
      <tr>
        <td>${statusBadge}</td>
        <td><strong style="color: #ffffff;">${escapeHtml(sh.name || sh.candidate_id)}</strong></td>
        <td>${escapeHtml(sh.title)} at ${escapeHtml(sh.company)}</td>
        <td>${escapeHtml(sh.location)}, ${escapeHtml(sh.country)}</td>
        <td>${sh.years_of_experience} yrs</td>
        <td style="max-width: 260px; font-size: 0.8125rem; color: var(--text-muted);">
          ${sh.recruiter_notes ? escapeHtml(sh.recruiter_notes) : '<em>No notes added</em>'}
        </td>
        <td style="text-align: right;">
          <button class="btn btn-secondary" onclick="openCandidateModal('${sh.candidate_id}')" style="padding: 0.375rem 0.75rem; font-size: 0.75rem;">
            Edit 📝
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function renderRunsTable(runs) {
  const tbody = document.getElementById("runs-table-body");
  if (!tbody) return;

  if (runs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No saved runs in database. Re-running the pipeline will create new versioned scoring runs!
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = runs.map(r => {
    const isActive = Boolean(r.is_active);
    const statusTag = isActive 
      ? `<span class="badge-tag badge-emerald">ACTIVE</span>` 
      : `<span class="badge-tag badge-indigo">ARCHIVED</span>`;

    return `
      <tr>
        <td><strong style="font-family: 'JetBrains Mono', monospace; color: #ffffff;">${r.run_id}</strong></td>
        <td style="font-size: 0.8125rem; color: var(--text-muted);">${r.created_at}</td>
        <td style="font-size: 0.8125rem;">${escapeHtml(r.dataset_source || 'Default')}</td>
        <td>${r.valid_candidates} / ${r.total_candidates}</td>
        <td style="font-family: 'JetBrains Mono', monospace; color: var(--accent-emerald);">${r.top_score ? r.top_score.toFixed(4) : '--'}</td>
        <td style="font-family: 'JetBrains Mono', monospace; color: var(--accent-cyan);">${r.cutoff_score_100 ? r.cutoff_score_100.toFixed(4) : '--'}</td>
        <td style="font-size: 0.8125rem;">${r.execution_time_sec}s</td>
        <td>${statusTag}</td>
        <td style="text-align: right;">
          ${isActive ? '<span style="font-size: 0.75rem; color: var(--accent-emerald);">Current Active</span>' : `<button class="btn btn-secondary" onclick="activateRun('${r.run_id}')" style="padding: 0.375rem 0.75rem; font-size: 0.75rem;">Activate ⚡</button>`}
        </td>
      </tr>
    `;
  }).join("");
}

function renderConfigStudio(cfg) {
  if (!cfg) return;
  for (const [key, val] of Object.entries(cfg)) {
    if (key === "JD_QUERY") {
      const textarea = document.getElementById("jd-query-input");
      if (textarea) textarea.value = val;
    } else {
      const slider = document.getElementById(`slider-${key}`);
      const display = document.getElementById(`val-${key}`);
      if (slider) slider.value = val;
      if (display) display.innerText = typeof val === "number" ? val.toFixed(2) : val;
    }
  }
}

function updateSliderLabel(key) {
  const slider = document.getElementById(`slider-${key}`);
  const display = document.getElementById(`val-${key}`);
  if (slider && display) {
    display.innerText = parseFloat(slider.value).toFixed(2);
  }
}

function resetConfigDefaults() {
  const defaults = {
    CORE_FIT_WEIGHT: 0.55,
    TEXT_RELEVANCE_WEIGHT: 0.45,
    TITLE_WEIGHT: 0.25,
    SKILLS_WEIGHT: 0.25,
    CAREER_WEIGHT: 0.20,
    EXPERIENCE_WEIGHT: 0.15,
    LOCATION_WEIGHT: 0.10,
    EDUCATION_WEIGHT: 0.05
  };
  renderConfigStudio(defaults);
  showToast("Reset sliders to default weights.");
}

function renderHoneypotsTable(honeypots) {
  const tbody = document.getElementById("honeypot-table-body");
  if (!tbody) return;

  if (honeypots.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No honeypots detected. System clean!
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = honeypots.map(h => {
    return `
      <tr>
        <td><span class="badge-tag badge-rose">DISQUALIFIED</span></td>
        <td><strong style="font-family: 'JetBrains Mono', monospace; color: #ffffff;">${h.candidate_id}</strong></td>
        <td>${escapeHtml(h.title)} at ${escapeHtml(h.company)}</td>
        <td>${h.years_of_experience} yrs</td>
        <td>
          <span style="font-size: 0.8125rem; color: var(--accent-rose);">
            ⚠️ Trap Detected: Expert skill duration mismatch / Career timeline math inconsistency
          </span>
        </td>
        <td>
          <button class="btn btn-secondary" onclick="openCandidateModal('${h.candidate_id}')" style="padding: 0.375rem 0.75rem; font-size: 0.75rem;">
            Inspect
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function renderMetricsTab(stats) {
  if (!stats) return;

  const titleContainer = document.getElementById("title-chart-container");
  if (titleContainer && stats.top_titles) {
    const sortedTitles = Object.entries(stats.top_titles).sort((a, b) => b[1] - a[1]);
    const maxVal = Math.max(...sortedTitles.map(t => t[1]), 1);

    titleContainer.innerHTML = sortedTitles.map(([title, count]) => {
      const pct = Math.round((count / maxVal) * 100);
      return `
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.8125rem; margin-bottom: 0.25rem;">
            <span style="font-weight: 600; color: #ffffff;">${escapeHtml(title)}</span>
            <span class="badge-tag badge-indigo">${count} candidates</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }).join("");
  }

  const countryContainer = document.getElementById("country-chart-container");
  if (countryContainer && stats.top_countries) {
    const sortedCountries = Object.entries(stats.top_countries).sort((a, b) => b[1] - a[1]);
    const maxVal = Math.max(...sortedCountries.map(c => c[1]), 1);

    countryContainer.innerHTML = sortedCountries.map(([country, count]) => {
      const pct = Math.round((count / maxVal) * 100);
      return `
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.8125rem; margin-bottom: 0.25rem;">
            <span style="font-weight: 600; color: #ffffff;">${escapeHtml(country)}</span>
            <span class="badge-tag badge-emerald">${count} candidates</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }).join("");
  }
}

// ============================================================================
// Modal Deep Dive
// ============================================================================

async function openCandidateModal(candidateId) {
  const c = await fetchCandidateById(candidateId);
  if (!c) {
    showToast("❌ Could not load candidate details");
    return;
  }
  state.selectedCandidate = c;

  const s = c.scores || {};
  document.getElementById("modal-candidate-name").innerText = c.name || c.candidate_id;
  document.getElementById("modal-candidate-sub").innerText = `${c.title} at ${c.company} • ${c.years_of_experience} yrs exp • ${c.location}, ${c.country}`;

  const rankBadge = document.getElementById("modal-rank-badge");
  const hpBadge = document.getElementById("modal-hp-badge");
  if (c.is_honeypot) {
    rankBadge.style.display = "none";
    hpBadge.style.display = "inline-flex";
  } else {
    rankBadge.style.display = "inline-flex";
    rankBadge.innerText = `Rank #${c.rank}`;
    hpBadge.style.display = "none";
  }

  document.getElementById("modal-final-score").innerText = s.final ? s.final.toFixed(4) : "0.0000";
  document.getElementById("modal-core-score").innerText = s.core_fit ? s.core_fit.toFixed(2) : "--";
  document.getElementById("modal-text-score").innerText = s.text_relevance ? s.text_relevance.toFixed(2) : "--";
  document.getElementById("modal-beh-score").innerText = s.behavioral ? s.behavioral.toFixed(2) + "x" : "--";

  document.getElementById("modal-reasoning").innerText = c.reasoning || "Reasoning analysis unavailable.";
  document.getElementById("modal-summary").innerText = c.summary || c.headline || "No summary provided.";

  // Recruiter Shortlist & Notes Box
  const statusSelect = document.getElementById("modal-shortlist-status");
  const notesInput = document.getElementById("modal-recruiter-notes");
  const starBtn = document.getElementById("modal-star-btn");
  if (statusSelect) statusSelect.value = c.shortlist_status || "none";
  if (notesInput) notesInput.value = c.recruiter_notes || "";
  if (starBtn) starBtn.classList.toggle("active", Boolean(c.is_starred));

  // Set 6 dimension bars
  setDimBar("title", s.title, 1.0);
  setDimBar("skills", s.skills, 1.0);
  setDimBar("career", s.career, 1.0);
  setDimBar("experience", s.experience, 1.0);
  setDimBar("location", s.location, 1.0);
  setDimBar("education", s.education, 1.0);

  // Render skills tags
  const skillsContainer = document.getElementById("modal-skills-tags");
  if (skillsContainer && c.skills) {
    skillsContainer.innerHTML = c.skills.map(sk => {
      const skName = typeof sk === "string" ? sk : sk.name;
      return `<span class="badge-tag badge-indigo" style="font-size: 0.8125rem;">${escapeHtml(skName)}</span>`;
    }).join("");
  }

  document.getElementById("candidate-modal").classList.add("active");
}

function setDimBar(name, val, maxVal) {
  const display = document.getElementById(`modal-dim-${name}`);
  const bar = document.getElementById(`modal-bar-${name}`);
  const score = val !== undefined ? val : 0;
  if (display) display.innerText = score.toFixed(2);
  if (bar) bar.style.width = `${Math.min((score / maxVal) * 100, 100)}%`;
}

function closeModal() {
  document.getElementById("candidate-modal").classList.remove("active");
}

function closeModalOnOverlay(e) {
  if (e.target.id === "candidate-modal") {
    closeModal();
  }
}

// ============================================================================
// Tab Navigation & Filter Events
// ============================================================================

function switchTab(tab) {
  state.activeTab = tab;

  // Toggle nav button states
  document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.remove("active"));
  const activeNav = document.getElementById(`tab-${tab}-btn`);
  if (activeNav) activeNav.classList.add("active");

  // Toggle tab panel visibility
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));
  const activePanel = document.getElementById(`panel-${tab}`);
  if (activePanel) activePanel.classList.add("active");

  if (tab === "shortlist") {
    fetchShortlists();
  } else if (tab === "runs") {
    fetchRuns();
    fetchDbStatus();
  }
}

let searchDebounceTimeout = null;
function handleSearchInput() {
  clearTimeout(searchDebounceTimeout);
  searchDebounceTimeout = setTimeout(() => {
    state.search = document.getElementById("search-input").value;
    state.page = 1;
    fetchCandidates();
  }, 250);
}

function handleFilterChange() {
  state.titleFilter = document.getElementById("filter-title").value;
  state.countryFilter = document.getElementById("filter-country").value;
  state.expFilter = document.getElementById("filter-exp").value;
  state.topOnly = document.getElementById("filter-top100").checked;
  state.starredOnly = document.getElementById("filter-starred").checked;
  state.page = 1;
  fetchCandidates();
}

function changePage(delta) {
  const newPage = state.page + delta;
  if (newPage >= 1 && newPage <= state.totalPages) {
    state.page = newPage;
    fetchCandidates();
  }
}

// ============================================================================
// Utilities
// ============================================================================

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<span>${message}</span>`;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(20px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
