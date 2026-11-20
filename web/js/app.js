import { state } from './state.js';
import { api } from './api.js';
import { SSEClient } from './sse.js';
import { scene3D } from './scene.js';
import { viewManager } from './views.js';
import { renderReport } from './render-report.js';
import { renderSourcesList, renderConflictsList, renderVerificationList, renderDebateView } from './panels.js';

// DOM Elements
const el = {
  canvasWebgl: null,
  css3dContainer: null,
  themeBtn: null,
  navDeckBtn: null,
  navReportBtn: null,
  navGraphBtn: null,
  btnStartResearch: null,
  globeCaption: null,
  floatingCardsLeft: null,
  floatingCardsRight: null,
  panelComposer: null,
  panelHistory: null,
  panelTelemetry: null,

  // Composer
  composerTextarea: null,
  btnSubmit: null,
  btnPreScrape: null,
  modeSelect: null,
  langSelect: null,
  modelSelect: null,
  approvalToggle: null,
  memoryToggle: null,
  docsToggle: null,
  promptChips: null,

  // Trace
  traceList: null,
  btnPauseScroll: null,
  btnCancelResearch: null,
  traceEtaVal: null,
  tracePercentVal: null,

  // Search Overlay
  searchOverlay: null,
  searchStatusTitle: null,
  searchSubStatus: null,
  searchProgressFill: null,
  searchPercentText: null,
  searchEtaText: null,

  // Decision Modal
  decisionModal: null,
  decisionSourcesList: null,
  btnCloseDecision: null,
  btnDecisionAi: null,
  btnDecisionManual: null,

  // Plan modal
  planModal: null,
  planQuestionsList: null,
  btnApprovePlan: null,

  // Report & Panels
  reportContainer: null,
  reportTabsNav: null,
  tabReportContent: null,
  tabSourcesContent: null,
  tabConflictsContent: null,
  tabVerificationContent: null,

  // Telemetry
  statTokens: null,
  statCost: null,
  statElapsed: null,
  statVerified: null,
  statSources: null,
  statConfidence: null,

  // History & Docs
  historyList: null,
  docsList: null,
  docFileInput: null,
  pdfDropzone: null,

  // Export
  exportBtnMd: null,
  exportBtnDocx: null,
  exportBtnPdf: null,
  btnCopyReport: null,
  toastContainer: null
};

function initDomElements() {
  el.canvasWebgl = document.getElementById('canvas-webgl');
  el.css3dContainer = document.getElementById('css3d-container');
  el.themeBtn = document.getElementById('theme-toggle-btn');
  el.navDeckBtn = document.getElementById('nav-deck-btn');
  el.navReportBtn = document.getElementById('nav-report-btn');
  el.navGraphBtn = document.getElementById('nav-graph-btn');
  el.btnStartResearch = document.getElementById('btn-start-research');
  el.globeCaption = document.getElementById('globe-idle-caption');
  el.floatingCardsLeft = document.getElementById('floating-cards-left');
  el.floatingCardsRight = document.getElementById('floating-cards-right');
  el.panelComposer = document.getElementById('panel-composer');
  el.panelHistory = document.getElementById('panel-history');
  el.panelTelemetry = document.getElementById('panel-telemetry');

  el.composerTextarea = document.getElementById('composer-textarea');
  el.btnSubmit = document.getElementById('btn-submit-research');
  el.btnPreScrape = document.getElementById('btn-pre-scrape');
  el.modeSelect = document.getElementById('mode-select');
  el.langSelect = document.getElementById('lang-select');
  el.modelSelect = document.getElementById('model-select');
  el.approvalToggle = document.getElementById('toggle-approval');
  el.memoryToggle = document.getElementById('toggle-memory');
  el.docsToggle = document.getElementById('toggle-docs');
  el.promptChips = document.querySelectorAll('.chip');

  el.traceList = document.getElementById('trace-events-list');
  el.btnPauseScroll = document.getElementById('btn-pause-scroll');
  el.btnCancelResearch = document.getElementById('btn-cancel-research');
  el.traceEtaVal = document.getElementById('trace-eta-val');
  el.tracePercentVal = document.getElementById('trace-percent-val');

  el.searchOverlay = document.getElementById('search-overlay');
  el.searchStatusTitle = document.getElementById('search-status-title');
  el.searchSubStatus = document.getElementById('search-sub-status');
  el.searchProgressFill = document.getElementById('search-progress-fill');
  el.searchPercentText = document.getElementById('search-percent-text');
  el.searchEtaText = document.getElementById('search-eta-text');

  el.planModal = document.getElementById('plan-modal');
  el.planQuestionsList = document.getElementById('plan-questions-list');
  el.btnApprovePlan = document.getElementById('btn-approve-plan');

  el.decisionModal = document.getElementById('decision-modal');
  el.decisionSourcesList = document.getElementById('decision-sources-list');
  el.btnCloseDecision = document.getElementById('btn-close-decision');
  el.btnDecisionAi = document.getElementById('btn-decision-ai');
  el.btnDecisionManual = document.getElementById('btn-decision-manual');

  el.reportContainer = document.getElementById('report-container');
  el.reportTabsNav = document.getElementById('report-tabs-nav');
  el.tabReportContent = document.getElementById('tab-report-content');
  el.tabSourcesContent = document.getElementById('tab-sources-content');
  el.tabConflictsContent = document.getElementById('tab-conflicts-content');
  el.tabVerificationContent = document.getElementById('tab-verification-content');

  el.statTokens = document.getElementById('stat-tokens');
  el.statCost = document.getElementById('stat-cost');
  el.statElapsed = document.getElementById('stat-elapsed');
  el.statVerified = document.getElementById('stat-verified');
  el.statSources = document.getElementById('stat-sources');
  el.statConfidence = document.getElementById('stat-confidence');

  el.historyList = document.getElementById('history-list');
  el.docsList = document.getElementById('docs-list');
  el.docFileInput = document.getElementById('doc-file-input');
  el.pdfDropzone = document.getElementById('pdf-dropzone');

  el.exportBtnMd = document.getElementById('btn-export-md');
  el.exportBtnDocx = document.getElementById('btn-export-docx');
  el.exportBtnPdf = document.getElementById('btn-export-pdf');
  el.btnCopyReport = document.getElementById('btn-copy-report');
  el.toastContainer = document.getElementById('toast-container');
}

let sseClient = null;
let isScrollPaused = false;
let currentRun = null;
let isPanelsVisible = false;

function togglePanelsVisibility() {
  // If user is on a different view (like running or report), always show panels in idle view
  if (viewManager.currentView !== 'idle') {
    showPanelsAction();
  } else if (isPanelsVisible) {
    hidePanelsAction();
  } else {
    showPanelsAction();
  }
}

function showPanelsAction() {
  isPanelsVisible = true;

  // Update button text and state
  if (el.btnStartResearch) {
    el.btnStartResearch.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      <span>Hide Panels</span>
    `;
    el.btnStartResearch.classList.remove('btn-primary');
    el.btnStartResearch.classList.add('btn-secondary');
  }

  // Hide idle caption and floating cards
  el.globeCaption?.classList.add('hidden');
  el.floatingCardsLeft?.classList.add('hidden');
  el.floatingCardsRight?.classList.add('hidden');

  // Dim and push globe back in 3D
  scene3D.setGlobeDimmed(true);

  const panels = [el.panelComposer, el.panelHistory, el.panelTelemetry];
  panels.forEach(panelEl => {
    if (!panelEl) return;
    panelEl.classList.remove('panel-idle-hidden');
    panelEl.removeAttribute('tabindex');
    panelEl.style.display = 'flex';
    panelEl.style.pointerEvents = 'auto';
  });

  // Switch to idle view so camera moves to composer and idle panels are shown
  viewManager.goTo('idle');

  // Focus textarea for keyboard accessibility
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  setTimeout(() => {
    el.composerTextarea?.focus();
  }, prefersReduced ? 10 : 250);
}

function hidePanelsAction() {
  isPanelsVisible = false;

  // Restore button text and state
  if (el.btnStartResearch) {
    el.btnStartResearch.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      <span>Start Research</span>
    `;
    el.btnStartResearch.classList.remove('btn-secondary');
    el.btnStartResearch.classList.add('btn-primary');
  }

  // Restore globe brightness and position
  scene3D.setGlobeDimmed(false);

  // Hide panels
  [el.panelComposer, el.panelHistory, el.panelTelemetry].forEach(p => {
    if (p) {
      p.classList.add('panel-idle-hidden');
      p.setAttribute('tabindex', '-1');
    }
  });

  scene3D.setView('idle');

  // Return focus to Start Research button
  el.btnStartResearch?.focus();
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    initDomElements();
    initTheme();
    setupEventListeners();

    // Initialize 3D Scene
    await scene3D.init(el.canvasWebgl, el.css3dContainer);

    loadHistory().catch(e => console.warn('History load failed:', e));
    loadDocuments().catch(e => console.warn('Docs load failed:', e));

    // Pre-populate latest history or sample report so Report view always has content ready
    api.getHistory().then(async (historyItems) => {
      if (historyItems && historyItems.length > 0) {
        const latest = await api.getHistoryDetail(historyItems[0].id);
        currentRun = { id: `${historyItems[0].id}`, topic: historyItems[0].topic, result: latest };
        displayResults(latest);
      }
      // Ensure we remain in idle/deck view on initial load unless demo param is set
      if (!state.get().isDemo) {
        viewManager.goTo('idle');
      }
    }).catch(() => {
      if (!state.get().isDemo) {
        viewManager.goTo('idle');
      }
    });

    if (state.get().isDemo) {
      loadDemoRun();
    }
  } catch (err) {
    console.error('App init error:', err);
  }
});

function initTheme() {
  document.documentElement.setAttribute('data-theme', state.get().theme);
  el.themeBtn?.addEventListener('click', () => state.toggleTheme());
}

function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = `<span>${msg}</span>`;
  el.toastContainer.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

function setupEventListeners() {
  el.btnStartResearch?.addEventListener('click', togglePanelsVisibility);

  // Deck view button: switches camera and view back to Deck / Idle view
  el.navDeckBtn?.addEventListener('click', () => {
    if (isPanelsVisible) {
      hidePanelsAction();
    }
    viewManager.goTo('idle');
  });

  // 3D Graph view button: switches camera to 3D Knowledge Graph perspective
  el.navGraphBtn?.addEventListener('click', () => {
    if (isPanelsVisible) {
      hidePanelsAction();
    }
    viewManager.goTo('graph');
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isPanelsVisible && viewManager.currentView === 'idle') {
      hidePanelsAction();
    }
  });

  el.navReportBtn?.addEventListener('click', async () => {
    const prose = document.getElementById('report-prose');
    const isProseEmpty = !prose || !prose.innerHTML.trim();

    if (currentRun?.result && !isProseEmpty) {
      viewManager.goTo('report');
      return;
    }

    if (currentRun?.result) {
      displayResults(currentRun.result);
      return;
    }

    try {
      const historyItems = await api.getHistory();
      if (historyItems && historyItems.length > 0) {
        const latest = await api.getHistoryDetail(historyItems[0].id);
        currentRun = { id: `${historyItems[0].id}`, topic: historyItems[0].topic, result: latest };
        displayResults(latest);
        return;
      }
    } catch (e) {
      console.warn('History load failed:', e);
    }

    showToast('No research report generated yet. Run a research first!', 'info');
  });

  el.btnSubmit.addEventListener('click', startPreScrapeFlow);
  el.composerTextarea.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      startPreScrapeFlow();
    }
  });

  el.promptChips.forEach(chip => {
    chip.addEventListener('click', () => {
      el.composerTextarea.value = chip.textContent.trim();
      el.composerTextarea.focus();
    });
  });

  // Report sub-tabs
  el.reportTabsNav?.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');
      switchReportTab(tab);
    });
  });

  // Decision Modal events
  el.btnPreScrape?.addEventListener('click', startPreScrapeFlow);
  el.btnCloseDecision?.addEventListener('click', () => {
    el.decisionModal?.classList.remove('open');
  });
  el.btnDecisionAi?.addEventListener('click', () => {
    el.decisionModal?.classList.remove('open');
    startDirectAiResearchFlow();
  });
  el.btnDecisionManual?.addEventListener('click', exportPreScrapeDossier);

  // Plan modal
  el.btnApprovePlan?.addEventListener('click', approvePlanAction);

  // Trace auto scroll & cancel
  el.btnPauseScroll?.addEventListener('click', () => {
    isScrollPaused = !isScrollPaused;
    el.btnPauseScroll.textContent = isScrollPaused ? 'Resume Scroll' : 'Pause Scroll';
  });

  el.btnCancelResearch?.addEventListener('click', async () => {
    if (currentRun?.id) {
      await api.cancelResearch(currentRun.id);
      showToast('Research cancelled', 'warning');
      if (el.btnStartResearch) {
        el.btnStartResearch.disabled = false;
        el.btnStartResearch.style.opacity = '1';
      }
      viewManager.goTo('idle');
    }
  });

  // PDF Dropzone
  if (el.pdfDropzone) {
    el.pdfDropzone.addEventListener('click', () => el.docFileInput.click());
    el.pdfDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      el.pdfDropzone.style.borderColor = 'var(--accent-primary)';
    });
    el.pdfDropzone.addEventListener('dragleave', () => {
      el.pdfDropzone.style.borderColor = 'var(--border-default)';
    });
    el.pdfDropzone.addEventListener('drop', async (e) => {
      e.preventDefault();
      el.pdfDropzone.style.borderColor = 'var(--border-default)';
      const file = e.dataTransfer.files[0];
      if (file && file.name.endsWith('.pdf')) {
        await handlePdfUpload(file);
      }
    });
  }

  el.docFileInput?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (file) await handlePdfUpload(file);
  });

  // Export buttons
  el.exportBtnMd?.addEventListener('click', () => downloadExport('md'));
  el.exportBtnDocx?.addEventListener('click', () => downloadExport('docx'));
  el.exportBtnPdf?.addEventListener('click', () => downloadExport('pdf'));
  el.btnCopyReport?.addEventListener('click', () => {
    if (currentRun?.result?.report) {
      navigator.clipboard.writeText(currentRun.result.report);
      showToast('Report copied to clipboard!');
    }
  });
}

function switchReportTab(tabName) {
  el.reportTabsNav?.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-tab') === tabName);
  });
  el.tabReportContent.style.display = tabName === 'report' ? 'block' : 'none';
  el.tabSourcesContent.style.display = tabName === 'sources' ? 'block' : 'none';
  el.tabConflictsContent.style.display = tabName === 'conflicts' ? 'block' : 'none';
  el.tabVerificationContent.style.display = tabName === 'verification' ? 'block' : 'none';
}

async function handlePdfUpload(file) {
  try {
    await api.uploadDocument(file);
    showToast(`Uploaded ${file.name}`);
    loadDocuments();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Research Progress and Dynamic ETA State
let searchStartTime = 0;
let estimatedTotalSeconds = 30;
let lastProgressPercent = 5;

function showSearchOverlay(initialTitle = 'Searching...', initialSub = 'Deploying multi-agent research swarm...') {
  if (!el.searchOverlay) return;
  searchStartTime = Date.now();
  lastProgressPercent = 5;
  if (el.searchStatusTitle) el.searchStatusTitle.textContent = initialTitle;
  if (el.searchSubStatus) el.searchSubStatus.textContent = initialSub;
  updateSearchProgress(8, initialSub);
  el.searchOverlay.classList.add('open');
}

function hideSearchOverlay() {
  if (!el.searchOverlay) return;
  el.searchOverlay.classList.remove('open');
}

function updateSearchProgress(targetPercent, subMsg = null, titleMsg = null) {
  if (!el.searchOverlay) return;

  if (targetPercent > lastProgressPercent) {
    lastProgressPercent = targetPercent;
  }
  const pct = Math.min(Math.max(lastProgressPercent, 5), 100);

  if (el.searchProgressFill) {
    el.searchProgressFill.style.width = `${pct}%`;
  }
  if (el.searchPercentText) {
    el.searchPercentText.textContent = `${pct}% done (${100 - pct}% remaining)`;
  }
  if (titleMsg && el.searchStatusTitle) {
    el.searchStatusTitle.textContent = titleMsg;
  }
  if (subMsg && el.searchSubStatus) {
    el.searchSubStatus.textContent = subMsg;
  }

  // Calculate dynamic ETA
  const elapsedSec = (Date.now() - searchStartTime) / 1000;
  let remainingSec = 0;
  if (pct >= 100) {
    remainingSec = 0;
  } else {
    // Dynamic projection based on elapsed and current fraction
    const projectedTotal = (elapsedSec / (pct / 100));
    const smoothTotal = Math.max(projectedTotal, estimatedTotalSeconds);
    remainingSec = Math.max(Math.round(smoothTotal - elapsedSec), 2);
  }

  if (el.searchEtaText) {
    if (pct >= 100) {
      el.searchEtaText.textContent = 'Completing dossier...';
    } else {
      el.searchEtaText.textContent = `~${remainingSec}s remaining`;
    }
  }

  // Update trace HUD timer badge in running view
  if (el.traceEtaVal) {
    el.traceEtaVal.textContent = pct >= 100 ? 'Done' : `~${remainingSec}s`;
  }
  if (el.tracePercentVal) {
    el.tracePercentVal.textContent = `${pct}%`;
  }
}

let latestPreScrapeData = null;

async function startPreScrapeFlow() {
  const query = el.composerTextarea.value.trim();
  if (!query) {
    el.composerTextarea.focus();
    return;
  }

  showSearchOverlay('Scraping Intelligence...', 'Running zero-API web extraction across top sources');
  updateSearchProgress(35, 'Searching DuckDuckGo and reading pages...');

  try {
    const data = await api.preScrape(query);
    latestPreScrapeData = data;
    hideSearchOverlay();
    openDecisionModal(data);
  } catch (err) {
    hideSearchOverlay();
    showToast(`Pre-scrape failed: ${err.message}`, 'error');
  }
}

function openDecisionModal(data) {
  if (!el.decisionModal || !el.decisionSourcesList) return;

  el.decisionSourcesList.innerHTML = '';
  const sources = data.sources || [];

  if (sources.length === 0) {
    el.decisionSourcesList.innerHTML = `
      <div style="padding:16px; text-align:center; color:var(--text-muted); font-size:13px;">
        No live sources extracted. You can still complete with AI or try another search query.
      </div>
    `;
  } else {
    sources.forEach((s, idx) => {
      const card = document.createElement('div');
      card.className = 'glass-panel';
      card.style.cssText = 'padding:14px 16px; min-height:auto; height:auto; overflow:visible; background:var(--bg-surface); border:1px solid var(--border-default); border-radius:var(--radius-md); box-sizing:border-box; flex-shrink:0;';

      const excerptsHtml = (s.key_excerpts || []).map(exc =>
        `<li style="margin-bottom:6px; font-size:12.5px; color:var(--text-secondary); line-height:1.5; word-break:break-word;">"${escapeHtml(exc)}"</li>`
      ).join('');

      const labelBadge = (s.label || 'Medium').toLowerCase();
      const badgeColor = labelBadge === 'high' ? '#10b981' : (labelBadge === 'medium' ? '#f59e0b' : '#ef4444');
      const badgeBg = labelBadge === 'high' ? 'rgba(16, 185, 129, 0.15)' : (labelBadge === 'medium' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)');

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:8px;">
          <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" style="font-weight:600; font-size:13.5px; color:var(--accent-primary); text-decoration:none; line-height:1.4; word-break:break-word; flex:1;">
            ${idx + 1}. ${escapeHtml(s.title || s.url)} ↗
          </a>
          <span style="display:inline-block; white-space:nowrap; padding:3px 10px; border-radius:12px; background:${badgeBg}; color:${badgeColor}; font-size:11.5px; font-weight:600; font-family:var(--font-mono); border:1px solid ${badgeColor}40; flex-shrink:0;">
            ${escapeHtml(s.label || 'Medium')} (${s.score || '0.5'})
          </span>
        </div>
        <div style="font-size:11.5px; color:var(--text-muted); margin-bottom:8px; line-height:1.4;">
          Domain: <code>${escapeHtml(s.domain_type || 'web')}</code> ${s.published ? `• Date: ${escapeHtml(s.published)}` : ''}
        </div>
        <ul style="padding-left:18px; margin:0; list-style-type:disc;">
          ${excerptsHtml || `<li style="font-size:12px; color:var(--text-muted);">${escapeHtml(s.snippet || 'No text excerpt extracted')}</li>`}
        </ul>
      `;
      el.decisionSourcesList.appendChild(card);
    });
  }

  el.decisionModal.classList.add('open');
}

async function exportPreScrapeDossier() {
  if (!latestPreScrapeData || !latestPreScrapeData.raw_markdown) {
    showToast('No raw dossier available to export', 'error');
    return;
  }

  const formatSelect = document.getElementById('export-format-select');
  const format = formatSelect ? formatSelect.value : 'pdf';
  const safeTitle = (latestPreScrapeData.query || 'Research').replace(/[^a-zA-Z0-9_-]/g, '_');

  showToast(`Generating ${format.toUpperCase()} export...`, 'info');

  try {
    if (format === 'md') {
      const blob = new Blob([latestPreScrapeData.raw_markdown], { type: 'text/markdown;charset=utf-8' });
      triggerBlobDownload(blob, `${safeTitle}_Raw_Intelligence.md`);
    } else {
      const blob = await api.exportRawDossier(latestPreScrapeData.raw_markdown, `${safeTitle}_Raw_Intelligence`, format);
      triggerBlobDownload(blob, `${safeTitle}_Raw_Intelligence.${format}`);
    }
    showToast(`Dossier downloaded as ${format.toUpperCase()}!`, 'success');
  } catch (err) {
    showToast(`Export failed: ${err.message}`, 'error');
  }
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function startDirectAiResearchFlow() {
  const query = el.composerTextarea.value.trim();
  if (!query) {
    el.composerTextarea.focus();
    return;
  }

  viewManager.goTo('running');
  el.traceList.innerHTML = '';
  if (el.btnStartResearch) {
    el.btnStartResearch.disabled = true;
    el.btnStartResearch.style.opacity = '0.5';
  }

  showSearchOverlay('AI Synthesis Active...', 'Running multi-agent AI verification & synthesis');

  try {
    const res = await api.startResearch({
      query,
      mode: el.modeSelect.value,
      language: el.langSelect.value,
      model: el.modelSelect.value || null,
      require_approval: el.approvalToggle.checked,
      use_memory: el.memoryToggle.checked,
      attach_docs: el.docsToggle.checked,
      parallel: false
    });

    currentRun = { id: res.id, topic: query, events: [], result: null };
    listenToStream(res.id);
  } catch (err) {
    hideSearchOverlay();
    showToast(err.message, 'error');
    if (el.btnStartResearch) {
      el.btnStartResearch.disabled = false;
      el.btnStartResearch.style.opacity = '1';
    }
    viewManager.goTo('idle');
  }
}

async function startResearchFlow() {
  await startPreScrapeFlow();
}

function listenToStream(runId) {
  if (sseClient) sseClient.close();

  sseClient = new SSEClient(
    runId,
    (event) => handleIncomingEvent(event),
    async () => {
      updateSearchProgress(100, 'Dossier ready! Finalizing report views...', 'Complete!');
      setTimeout(() => {
        hideSearchOverlay();
      }, 600);

      showToast('Research Complete!', 'success');
      if (el.btnStartResearch) {
        el.btnStartResearch.disabled = false;
        el.btnStartResearch.style.opacity = '1';
      }
      const full = await api.getResearch(runId);
      currentRun = full;
      displayResults(full.result);
      loadHistory();
    },
    (err) => {
      showToast('Reconnecting...', 'warning');
      if (el.btnStartResearch) {
        el.btnStartResearch.disabled = false;
        el.btnStartResearch.style.opacity = '1';
      }
      api.getResearch(runId).then(full => {
        if (full.status === 'done') {
          hideSearchOverlay();
          displayResults(full.result);
        }
      });
    }
  );
  sseClient.connect();
}

function handleIncomingEvent(ev) {
  currentRun.events.push(ev);
  appendTraceEvent(ev);
  updateDrawerStats(ev);

  if (ev.agent) {
    scene3D.triggerAgentActive(ev.agent);
  }

  // Update Searching Overlay Progress and Time Estimation based on Agent Pipeline Stage
  const agentLower = (ev.agent || '').toLowerCase();
  const kind = (ev.kind || '').toLowerCase();
  const msg = (ev.message || ev.msg || '').toLowerCase();

  if (agentLower === 'planner' || kind === 'plan') {
    updateSearchProgress(18, 'Formulating research vectors and sub-questions...', 'Planning Research...');
  } else if (agentLower === 'researcher' || agentLower === 'researchers' || kind === 'tool') {
    // Dynamic jump within 25% to 65%
    const currentPct = lastProgressPercent < 25 ? 28 : Math.min(lastProgressPercent + 7, 65);
    const detailMsg = ev.message || 'Scraping and analyzing verified web intelligence...';
    updateSearchProgress(currentPct, detailMsg, 'Searching & Gathering Evidence...');
  } else if (agentLower === 'analyzer' || kind === 'scores') {
    updateSearchProgress(72, 'Cross-examining claims and scoring credibility...', 'Analyzing Evidence...');
  } else if (agentLower === 'writer' || kind === 'draft') {
    updateSearchProgress(84, 'Synthesizing verified dossier and citations...', 'Writing Synthesis...');
  } else if (agentLower === 'verifier' || kind === 'claim_check') {
    updateSearchProgress(93, 'Validating claim proofs against raw sources...', 'Verifying Factuality...');
  } else if (kind === 'done' || msg.includes('complete')) {
    updateSearchProgress(100, 'All agents finished. Compiling report...', 'Finalizing...');
  }

  if (ev.kind === 'awaiting_approval' || ev.status === 'awaiting_approval') {
    hideSearchOverlay();
    openPlanModal(ev.pending);
  } else {
    // Make sure overlay stays open during research execution after plan is approved or bypassed
    if (el.searchOverlay && !el.searchOverlay.classList.contains('open') && (!el.planModal || !el.planModal.classList.contains('open'))) {
      el.searchOverlay.classList.add('open');
    }
  }
}

function appendTraceEvent(ev) {
  const item = document.createElement('div');
  const agentClass = (ev.agent || 'system').toLowerCase();
  item.className = `trace-event ${agentClass}`;
  const timeStr = `${ev.timestamp || ev.t || 0}s`;

  item.innerHTML = `
    <span style="color:var(--text-muted); font-size:12px; flex-shrink:0; font-family:var(--font-mono);">${timeStr}</span>
    <span class="badge trace-badge" style="background:var(--bg-surface-elevated);">${ev.agent || 'Agent'}</span>
    <span class="trace-msg" style="flex:1; word-break:break-word;">${escapeHtml(ev.message || ev.msg || '')}</span>
  `;

  el.traceList.appendChild(item);
  if (!isScrollPaused) {
    el.traceList.scrollTop = el.traceList.scrollHeight;
  }
}

function updateDrawerStats(ev) {
  if (ev.tokens) el.statTokens.textContent = ev.tokens.toLocaleString();
  if (ev.cost !== undefined) el.statCost.textContent = `$${ev.cost.toFixed(4)}`;
  if (ev.timestamp) el.statElapsed.textContent = `${ev.timestamp}s`;
}

function openPlanModal(pending) {
  viewManager.goTo('plan');
  el.planQuestionsList.innerHTML = '';
  const qs = (pending && pending.plan) || [];
  qs.forEach(q => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex; gap:8px; margin-bottom:8px;';
    row.innerHTML = `<input type="text" class="input plan-q-input" value="${escapeHtml(q)}" />`;
    el.planQuestionsList.appendChild(row);
  });
  el.planModal.classList.add('open');
}

async function approvePlanAction() {
  const inputs = el.planQuestionsList.querySelectorAll('.plan-q-input');
  const subQuestions = Array.from(inputs).map(i => i.value.trim()).filter(Boolean);
  el.planModal.classList.remove('open');
  showSearchOverlay('Searching...', 'Angles approved. Researchers deploying across web...');
  updateSearchProgress(28, 'Spawning parallel web scrapers...');
  viewManager.goTo('running');

  try {
    await api.approvePlan(currentRun.id, subQuestions);
    showToast('Plan approved!');
  } catch (err) {
    hideSearchOverlay();
    showToast(err.message, 'error');
  }
}

function displayResults(res) {
  if (!res) return;
  hideSearchOverlay();
  viewManager.goTo('report');

  // Telemetry
  el.statTokens.textContent = (res.tokens || 0).toLocaleString();
  el.statCost.textContent = `$${(res.cost_usd || 0).toFixed(4)}`;
  el.statElapsed.textContent = `${res.elapsed || 0}s`;
  el.statSources.textContent = (res.sources || []).length;
  el.statConfidence.textContent = res.confidence || 'Verified';
  const ratio = res.verification?.ratio ? Math.round(res.verification.ratio * 100) : 100;
  el.statVerified.textContent = `${ratio}%`;

  // Enable Export
  [el.btnCopyReport, el.exportBtnMd, el.exportBtnDocx, el.exportBtnPdf].forEach(b => {
    if (b) b.disabled = false;
  });

  // Render Report & Tabs
  const runMeta = {
    id: res.id || currentRun?.id,
    topic: res.topic || currentRun?.topic,
    query: currentRun?.topic || res.topic,
    mode: res.mode || (res.debate ? 'debate' : 'standard'),
    language: res.language || res.lang || 'en',
    created_at: res.created_at,
    tokens: res.tokens,
    cost_usd: res.cost_usd !== undefined ? res.cost_usd : res.cost,
    sources: res.sources,
    verification: res.verification,
    retries: res.retries,
    debate: res.debate,
    model: res.model || currentRun?.model,
    require_approval: res.require_approval !== undefined ? res.require_approval : currentRun?.require_approval,
    use_memory: res.use_memory !== undefined ? res.use_memory : currentRun?.use_memory,
    attach_docs: res.attach_docs !== undefined ? res.attach_docs : currentRun?.attach_docs,
    plan: res.plan || currentRun?.plan,
    elapsed: res.elapsed
  };

  const debateSection = document.getElementById('report-debate-section');
  if (debateSection) {
    if (res.debate && (res.debate.pro || res.debate.con)) {
      renderDebateView(res.debate, debateSection);
    } else {
      debateSection.innerHTML = '';
    }
  }

  renderReport(res.report, res.source_scores || res.sources || [], res.claim_checks || [], null, runMeta);
  renderSourcesList(res.source_scores || res.sources || [], el.tabSourcesContent);
  renderConflictsList(res.conflicts || [], el.tabConflictsContent);
  renderVerificationList(res.claim_checks || [], el.tabVerificationContent);
}

async function loadHistory() {
  const items = await api.getHistory();
  el.historyList.innerHTML = '';
  if (!items || items.length === 0) {
    el.historyList.innerHTML = '<div style="color:var(--text-muted); font-size:13px; padding:8px 4px;">No past runs yet.</div>';
    return;
  }
  items.slice(0, 6).forEach(item => {
    const div = document.createElement('div');
    div.className = 'chip';
    div.style.cssText = 'width:100%; text-align:left; border-radius:6px; margin-bottom:4px; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;';
    div.textContent = item.topic;
    div.title = item.topic;
    div.addEventListener('click', async () => {
      const full = await api.getHistoryDetail(item.id);
      currentRun = { id: `${item.id}`, topic: item.topic, result: full };
      displayResults(full);
    });
    el.historyList.appendChild(div);
  });
}

async function loadDocuments() {
  const docs = await api.getDocuments();
  el.docsList.innerHTML = '';
  if (!docs || docs.length === 0) {
    el.docsList.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:4px;">No PDFs uploaded.</div>';
    return;
  }
  docs.forEach(doc => {
    const div = document.createElement('div');
    div.style.cssText = 'display:flex; justify-content:space-between; align-items:center; font-size:13px; padding:6px 8px; background:var(--bg-surface-elevated); border-radius:4px; margin-bottom:4px;';
    div.innerHTML = `<span>📄 ${doc.filename || doc.doc_id}</span>`;
    el.docsList.appendChild(div);
  });
}

async function loadDemoRun() {
  showToast('Loading 3D Demo...', 'info');
  const demo = await api.getDemoFixture();
  currentRun = demo;
  viewManager.goTo('running');
  el.traceList.innerHTML = '';

  demo.events.forEach((ev, i) => {
    setTimeout(() => {
      handleIncomingEvent(ev);
      if (i === demo.events.length - 1) {
        setTimeout(() => displayResults(demo.result), 600);
      }
    }, i * 280);
  });
}

async function downloadExport(fmt) {
  // If we have an active run id, try that first
  const runId = currentRun?.id || (currentRun?.result?.id);
  const reportText = currentRun?.result?.report || document.getElementById('report-markdown-body')?.innerText;

  if (runId && runId !== 'undefined') {
    window.open(api.getExportUrl(runId, fmt), '_blank');
    return;
  }

  // Fallback: If no runId is saved or running directly from view, export via direct raw conversion
  if (reportText) {
    const topic = currentRun?.topic || 'Research_Report';
    const safeTitle = topic.replace(/[^a-zA-Z0-9_-]/g, '_');
    showToast(`Downloading ${fmt.toUpperCase()}...`, 'info');
    try {
      if (fmt === 'md') {
        const blob = new Blob([reportText], { type: 'text/markdown;charset=utf-8' });
        triggerBlobDownload(blob, `${safeTitle}.md`);
      } else {
        const blob = await api.exportRawDossier(reportText, safeTitle, fmt);
        triggerBlobDownload(blob, `${safeTitle}.${fmt}`);
      }
      showToast(`${fmt.toUpperCase()} downloaded!`, 'success');
    } catch (err) {
      showToast(`Export failed: ${err.message}`, 'error');
    }
  } else {
    showToast('No report content available to export', 'warning');
  }
}

function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
