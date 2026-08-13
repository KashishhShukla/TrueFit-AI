/**
 * Intelligent Candidate Discovery & Ranking System - Frontend Application
 */

const API_BASE = ""; // Relative path for REST endpoints on same origin

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
  stats: null,
  config: null,
  honeypots: [],
  selectedCandidate: null
};

// DOM Initialization
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  await fetchStats();
  await fetchConfig();
  await fetchCandidates();
  await fetchHoneypots();
}

// ============================================================================
// API Calls
// ============================================================================

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
    top_only: state.topOnly ? "true" : "false"
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

async function fetchCandidateById(candidateId) {
  try {
    const res = await fetch(`${API_BASE}/api/candidates/${candidateId}`);
    return await res.json();
  } catch (err) {
    console.error(`Error fetching candidate ${candidateId}:`, err);
    return null;
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
    showToast("✅ Scoring pipeline completed! Leaderboard updated.");
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

// ============================================================================
// UI Render Functions
// ============================================================================

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
        <td colspan="7" style="text-align: center; padding: 3rem; color: var(--text-muted);">
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

    return `
      <tr>
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
  const start = (state.page - 1) * state.pageSize + 1;
  const end = Math.min(state.page * state.pageSize, state.totalCandidates);
  document.getElementById("pagination-info").innerText = `Showing ${start}-${end} of ${state.totalCandidates} candidates`;
  document.getElementById("page-num-display").innerText = `Page ${state.page} of ${state.totalPages}`;

  document.getElementById("prev-page-btn").disabled = state.page <= 1;
  document.getElementById("next-page-btn").disabled = state.page >= state.totalPages;
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

  // Render Top Titles Bar Chart
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

  // Render Top Countries
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
            <div class="progress-fill" style="width: ${pct}%; background: linear-gradient(90deg, var(--accent-emerald), var(--accent-cyan));"></div>
          </div>
        </div>
      `;
    }).join("");
  }
}

// ============================================================================
// Modal & Inspection
// ============================================================================

async function openCandidateModal(candidateId) {
  const candidate = await fetchCandidateById(candidateId);
  if (!candidate) return;

  state.selectedCandidate = candidate;

  document.getElementById("modal-candidate-name").innerText = candidate.name || candidate.candidate_id;
  document.getElementById("modal-candidate-sub").innerText = `${candidate.title} at ${candidate.company} • ${candidate.years_of_experience} yrs exp • ${candidate.location}, ${candidate.country}`;

  const rankBadge = document.getElementById("modal-rank-badge");
  const hpBadge = document.getElementById("modal-hp-badge");
  if (candidate.is_honeypot) {
    rankBadge.style.display = "none";
    hpBadge.style.display = "inline-flex";
  } else {
    rankBadge.style.display = "inline-flex";
    rankBadge.innerText = `Rank #${candidate.rank}`;
    hpBadge.style.display = "none";
  }

  const s = candidate.scores || {};
  document.getElementById("modal-final-score").innerText = s.final ? s.final.toFixed(4) : "0.0000";
  document.getElementById("modal-core-score").innerText = s.core_fit ? s.core_fit.toFixed(2) : "--";
  document.getElementById("modal-text-score").innerText = s.text_relevance ? s.text_relevance.toFixed(2) : "--";
  document.getElementById("modal-beh-score").innerText = s.behavioral ? s.behavioral.toFixed(2) + "x" : "--";

  document.getElementById("modal-reasoning").innerText = candidate.reasoning || "No reasoning generated.";

  // Core sub-scores
  setModalDim("title", s.title);
  setModalDim("skills", s.skills);
  setModalDim("career", s.career);
  setModalDim("experience", s.experience);
  setModalDim("location", s.location);
  setModalDim("education", s.education);

  // Skills
  const skillsContainer = document.getElementById("modal-skills-tags");
  if (candidate.skills && candidate.skills.length > 0) {
    skillsContainer.innerHTML = candidate.skills.map(sk => `<span class="badge-tag badge-indigo">${escapeHtml(sk)}</span>`).join("");
  } else {
    skillsContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 0.8125rem;">No skills listed</span>`;
  }

  document.getElementById("modal-summary").innerText = candidate.summary || candidate.headline || "No summary profile provided.";

  document.getElementById("candidate-modal").classList.add("active");
}

function setModalDim(dimKey, val) {
  const scoreVal = val || 0;
  const numElem = document.getElementById(`modal-dim-${dimKey}`);
  const barElem = document.getElementById(`modal-bar-${dimKey}`);
  if (numElem) numElem.innerText = scoreVal.toFixed(2);
  if (barElem) barElem.style.width = `${Math.min(scoreVal * 100, 100)}%`;
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
// Event Handlers & Helpers
// ============================================================================

function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));

  const targetBtn = document.getElementById(`tab-${tabName}-btn`);
  const targetPanel = document.getElementById(`panel-${tabName}`);
  if (targetBtn) targetBtn.classList.add("active");
  if (targetPanel) targetPanel.classList.add("active");
}

let searchDebounceTimer;
function handleSearchInput() {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    state.search = document.getElementById("search-input").value;
    state.page = 1;
    fetchCandidates();
  }, 300);
}

function applyFilters() {
  state.titleFilter = document.getElementById("filter-title").value;
  state.countryFilter = document.getElementById("filter-country").value;
  state.expFilter = document.getElementById("filter-exp").value;
  state.topOnly = document.getElementById("toggle-top100").checked;
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

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerText = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
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
