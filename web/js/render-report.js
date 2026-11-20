// Markdown Report Renderer
// Sticky H2/H3 TOC with IntersectionObserver, Interactive Citations Popovers,
// Report Header Banner with 5-Stat Summary Bar, Verified Claims Highlighting Toggle,
// Dynamic Badges (Mode with Run Details, Interactive Language Menu with Translation API,
// Localized Time with Duration Tooltip), Debate Mode Two-Column Layout,
// and Keyboard-Accessible Controls with localStorage persistence

import { api } from './api.js';

let activeObserver = null;
let currentRunMeta = {};
let originalMarkdown = '';
let currentTranslatedMarkdown = null;
let translationCache = new Map();

export function renderReport(markdown, sources = [], claimChecks = [], containerEl, runMeta = {}) {
  if (!markdown) return;

  currentRunMeta = runMeta || {};
  if (!currentTranslatedMarkdown) {
    originalMarkdown = markdown;
  }

  // 1. Build Source Map for instant lookup
  const sourceMap = new Map();
  sources.forEach((s, idx) => {
    const id = s.id || (idx + 1);
    sourceMap.set(id, s);
  });

  // 2. Extract Document Title from markdown H1 if present
  let title = runMeta.topic || runMeta.query || 'Executive Research Dossier';
  let cleanMarkdown = markdown;
  const h1Match = markdown.match(/^#\s+(.+)$/m);
  if (h1Match) {
    title = h1Match[1].trim();
    // Remove the leading H1 from the body prose so it isn't rendered twice
    cleanMarkdown = markdown.replace(/^#\s+.+$/m, '').trim();
  }

  // 3. Process citation chips [n] -> focusable, accessible interactive tags
  const processedMarkdown = cleanMarkdown.replace(/\[(\d+)\]/g, (match, p1) => {
    return `<a href="#source-${p1}" class="citation-chip" data-cite="${p1}" tabindex="0" role="button" aria-label="Citation source ${p1}">[${p1}]</a>`;
  });

  // 4. Parse Markdown to HTML via marked & sanitize via DOMPurify
  let rawHtml = '';
  if (window.marked) {
    window.marked.setOptions({ gfm: true, breaks: true });
    rawHtml = window.marked.parse(processedMarkdown);
  } else {
    rawHtml = processedMarkdown.replace(/\n\n/g, '<p></p>').replace(/\n/g, '<br/>');
  }

  const cleanHtml = window.DOMPurify 
    ? window.DOMPurify.sanitize(rawHtml, { ADD_ATTR: ['target', 'data-cite', 'tabindex', 'role', 'aria-label'] }) 
    : rawHtml;

  // 5. Populate Main Report Column and Header Banner
  const headerBanner = document.getElementById('report-header-banner');
  const reportProse = document.getElementById('report-prose');

  // Compute 5 Stats: Sources, Verified %, Retries, Tokens, Cost (Fallbacks: "—", never "undefined")
  const sourcesCount = sources.length > 0 ? sources.length : (runMeta.sources?.length || '—');
  
  let verifiedPct = '—';
  if (runMeta.verification && runMeta.verification.ratio !== undefined) {
    verifiedPct = `${Math.round(runMeta.verification.ratio * 100)}%`;
  } else if (claimChecks.length > 0) {
    const supported = claimChecks.filter(c => c.verdict === 'supported').length;
    verifiedPct = `${Math.round((supported / claimChecks.length) * 100)}%`;
  }

  let retriesCount = '—';
  if (claimChecks.length > 0) {
    retriesCount = claimChecks.reduce((acc, c) => acc + (c.retry || c.retries || 0), 0);
  } else if (runMeta.retries !== undefined) {
    retriesCount = runMeta.retries;
  }

  const tokensFormatted = runMeta.tokens ? runMeta.tokens.toLocaleString() : '—';
  const costFormatted = runMeta.cost_usd !== undefined 
    ? `$${Number(runMeta.cost_usd).toFixed(4)}` 
    : (runMeta.cost !== undefined ? `$${Number(runMeta.cost).toFixed(4)}` : '—');

  // Mode badge logic
  const isDebate = runMeta.mode === 'debate' || (runMeta.debate && (runMeta.debate.pro || runMeta.debate.con));
  const modeBadgeText = isDebate ? 'Debate Mode (PRO vs CON)' : 'Standard Mode';
  const modeClass = isDebate ? 'badge-debate' : 'badge-standard';

  // Language badge logic
  const langCode = (runMeta.language || runMeta.lang || 'en').toLowerCase();
  const langDisplayCode = langCode === 'hi' ? 'HI' : (langCode === 'hinglish' ? 'Hinglish' : (langCode ? langCode.toUpperCase() : 'EN'));

  // Time & Duration tooltip
  const createdDate = runMeta.created_at ? new Date(runMeta.created_at) : new Date();
  const timeFormatted = createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const fullDateTime = createdDate.toLocaleString([], { dateStyle: 'full', timeStyle: 'medium' });
  const durationText = runMeta.elapsed !== undefined ? `${runMeta.elapsed}s` : '—';
  const timeTooltip = `Generated: ${fullDateTime} | Total run duration: ${durationText}`;

  const originalQuery = runMeta.topic || runMeta.query || title;

  // Retrieve saved states from localStorage
  const savedHighlight = localStorage.getItem('rm_highlight_verified_claims') === 'true';
  const savedSideState = localStorage.getItem('rm_side_panel_state') || 'open'; // 'open' | 'closed'

  if (headerBanner) {
    headerBanner.innerHTML = `
      <div class="report-header-top-row">
        <div class="report-meta-badges">
          <!-- 1. Mode Badge Button (Interactive Popover) -->
          <button class="badge badge-btn ${modeClass}" id="btn-badge-mode" aria-label="View Run Details for ${escapeHtml(modeBadgeText)}" aria-haspopup="dialog" aria-expanded="false" title="Click to view run configuration details">
            <span>⚡ ${escapeHtml(modeBadgeText)}</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
          </button>

          <!-- Mode Details Popover -->
          <div class="badge-popover-container" id="popover-mode-details" role="dialog" aria-label="Run details">
            <div class="popover-title-row">Run Configuration Details</div>
            <div class="popover-details-grid">
              <div class="popover-detail-item">
                <span>Mode:</span>
                <strong>${isDebate ? 'Debate (PRO vs CON)' : 'Standard Mode'}</strong>
              </div>
              <div class="popover-detail-item">
                <span>Model:</span>
                <strong>${escapeHtml(runMeta.model || 'Groq Qwen 2.5 (Fastest)')}</strong>
              </div>
              <div class="popover-detail-item">
                <span>Plan Approval:</span>
                <strong>${runMeta.require_approval !== false ? 'ON' : 'OFF'}</strong>
              </div>
              <div class="popover-detail-item">
                <span>Memory (KG):</span>
                <strong>${runMeta.use_memory !== false ? 'ON' : 'OFF'}</strong>
              </div>
              <div class="popover-detail-item">
                <span>Local PDFs Used:</span>
                <strong>${runMeta.attach_docs ? 'YES' : 'NO'}</strong>
              </div>
              <div class="popover-detail-item">
                <span>Sub-questions:</span>
                <strong>${Array.isArray(runMeta.plan) ? runMeta.plan.length : (runMeta.sub_questions?.length || '—')}</strong>
              </div>
              <div class="popover-detail-item">
                <span>Verifier Retries:</span>
                <strong>${retriesCount}</strong>
              </div>
            </div>
          </div>

          <!-- 2. Language Badge Button (Interactive Menu with Translation API) -->
          <button class="badge-btn" id="btn-badge-lang" aria-label="Report Language: ${escapeHtml(langDisplayCode)}. Click to translate" aria-haspopup="menu" aria-expanded="false" title="Click to view report in another language">
            <span>🌐 ${escapeHtml(langDisplayCode)}</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
          </button>

          <!-- Language Menu Popover -->
          <div class="badge-popover-container" id="popover-lang-menu" role="menu" aria-label="Translate Report Language">
            <div class="popover-title-row">Report Language</div>
            <div class="lang-menu-list">
              <button class="lang-menu-item ${langCode === 'en' ? 'active' : ''}" data-lang="en">English (Original)</button>
              <button class="lang-menu-item ${langCode === 'hi' ? 'active' : ''}" data-lang="hi">Hindi (हिंदी)</button>
              <button class="lang-menu-item ${langCode === 'hinglish' ? 'active' : ''}" data-lang="hinglish">Hinglish</button>
              <button class="lang-menu-item" data-lang="auto">Auto Detect</button>
            </div>
          </div>

          <!-- 3. Time Badge (With Full Date & Duration Tooltip) -->
          <span class="report-meta-tag" id="badge-time" tabindex="0" role="note" aria-label="${escapeHtml(timeTooltip)}" title="${escapeHtml(timeTooltip)}">
            🕒 ${timeFormatted}
          </span>
        </div>

        <div class="report-header-actions-group">
          <!-- Toggle: Highlight verified claims -->
          <label class="switch report-claims-switch" title="Highlight verified (green) and weak (amber) statements in prose">
            <input type="checkbox" id="toggle-highlight-claims" ${savedHighlight ? 'checked' : ''} aria-label="Highlight verified claims in prose">
            <span class="switch-slider" tabindex="0" role="switch" aria-checked="${savedHighlight}"></span>
            <span class="switch-label-text">Highlight verified claims</span>
          </label>

          <!-- Evidence Button: Toggles Side Panel -->
          <button id="btn-toggle-side-panel" class="side-panel-toggle-btn" aria-label="Toggle Evidence Side Panel" aria-expanded="${savedSideState === 'open' ? 'true' : 'false'}" title="Toggle Evidence Side Panel (Sources, Contradictions, Verification)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="15" y1="3" x2="15" y2="21"/></svg>
            <span>Evidence</span>
          </button>
        </div>
      </div>

      <h1 class="report-title-heading">${escapeHtml(title)}</h1>

      <div class="report-query-banner">
        <span class="query-badge">INQUIRY</span>
        <span class="query-text">${escapeHtml(originalQuery)}</span>
      </div>

      <!-- 5-Stat Compact Summary Bar -->
      <div class="report-summary-bar">
        <div class="summary-stat-cell">
          <div class="stat-cell-label">Sources</div>
          <div class="stat-cell-value" id="stat-sum-sources">${sourcesCount}</div>
        </div>
        <div class="summary-stat-cell">
          <div class="stat-cell-label">Verified %</div>
          <div class="stat-cell-value stat-val-success" id="stat-sum-verified">${verifiedPct}</div>
        </div>
        <div class="summary-stat-cell">
          <div class="stat-cell-label">Retries</div>
          <div class="stat-cell-value" id="stat-sum-retries">${retriesCount}</div>
        </div>
        <div class="summary-stat-cell">
          <div class="stat-cell-label">Tokens</div>
          <div class="stat-cell-value" id="stat-sum-tokens">${tokensFormatted}</div>
        </div>
        <div class="summary-stat-cell">
          <div class="stat-cell-label">Cost</div>
          <div class="stat-cell-value stat-val-accent" id="stat-sum-cost">${costFormatted}</div>
        </div>
      </div>
    `;
  }

  // 6. Handle Debate Mode Layout vs Standard Prose Layout
  const debateContainer = document.getElementById('report-debate-section');
  if (isDebate && runMeta.debate && (runMeta.debate.pro || runMeta.debate.con)) {
    // In Debate Mode, render two-column PRO vs CON layout with verdict at the bottom
    renderDebateTwoColumnView(runMeta.debate, debateContainer);
  } else if (debateContainer) {
    debateContainer.innerHTML = '';
  }

  // 7. Inject clean HTML into prose
  if (reportProse) {
    reportProse.innerHTML = cleanHtml;
    if (savedHighlight) {
      reportProse.classList.add('highlight-verified-claims');
    } else {
      reportProse.classList.remove('highlight-verified-claims');
    }

    // Process Tables: responsive wrapper + auto table-layout + numeric nowrap
    const tables = reportProse.querySelectorAll('table');
    tables.forEach(table => {
      table.classList.add('report-table');
      if (!table.parentElement.classList.contains('report-table-wrapper')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'report-table-wrapper';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
      table.querySelectorAll('td').forEach(td => {
        const text = td.textContent.trim();
        if (/^[\$€£~]?\s*[\d,\.]+(%|\s*(points|Billion|Million|k|K|X|x|sales|points))?$/i.test(text) || !isNaN(Number(text.replace(/[\$,%~]/g, '')))) {
          td.classList.add('numeric-cell');
        }
      });
    });

    // Prepare Claim Highlights in text
    prepareClaimHighlights(reportProse, claimChecks);
  }

  // 8. Build TOC from H2 and H3 ONLY (excluding H1)
  buildTableOfContents(reportProse);

  // 9. Setup Citation Popovers & Side Panel Navigation
  setupCitationPopovers(reportProse, sourceMap, claimChecks);

  // 10. Wire Badge Interactions, Translation, Keyboard Accessibility & Panel Toggles
  wireBadgeInteractions(sources, claimChecks);
  wireReportToggles();

  // Apply remembered side panel state
  const panelReport = document.getElementById('panel-report');
  const btnToggleSide = document.getElementById('btn-toggle-side-panel');
  if (panelReport) {
    if (savedSideState === 'closed') {
      panelReport.classList.add('side-panel-collapsed');
      if (btnToggleSide) btnToggleSide.setAttribute('aria-expanded', 'false');
    } else {
      panelReport.classList.remove('side-panel-collapsed');
      if (btnToggleSide) btnToggleSide.setAttribute('aria-expanded', 'true');
    }
  }
}

function renderDebateTwoColumnView(debate, containerEl) {
  if (!containerEl || !debate) return;
  containerEl.innerHTML = '';

  const proPoints = Array.isArray(debate.pro) ? debate.pro : (debate.pro_findings || []);
  const conPoints = Array.isArray(debate.con) ? debate.con : (debate.con_findings || []);
  const verdict = debate.verdict || debate.consensus || 'Neutral / Inconclusive debate balance.';

  const debateWrap = document.createElement('div');
  debateWrap.className = 'debate-view-container';
  debateWrap.innerHTML = `
    <!-- Top Two-Column PRO vs CON Cards -->
    <div class="debate-cards-row">
      <div class="debate-arg-card pro-card">
        <h4 class="arg-header pro-header">🟢 PRO / SUPPORTING ARGUMENTS</h4>
        <div class="arg-points-list">
          ${proPoints.map(p => `
            <div class="arg-point-item">
              ${escapeHtml(typeof p === 'string' ? p : (p.claim || p.text || ''))}
            </div>
          `).join('') || '<div class="side-panel-empty-state">No pro arguments recorded.</div>'}
        </div>
      </div>
      <div class="debate-arg-card con-card">
        <h4 class="arg-header con-header">🔴 CON / OPPOSING ARGUMENTS</h4>
        <div class="arg-points-list">
          ${conPoints.map(c => `
            <div class="arg-point-item">
              ${escapeHtml(typeof c === 'string' ? c : (c.claim || c.text || ''))}
            </div>
          `).join('') || '<div class="side-panel-empty-state">No con arguments recorded.</div>'}
        </div>
      </div>
    </div>

    <!-- Consensus Verdict at Bottom -->
    <div class="debate-verdict-banner" style="margin-top: 14px;">
      <div class="verdict-label">SYNTHESIZED CONSENSUS VERDICT</div>
      <div class="verdict-text">${escapeHtml(verdict)}</div>
    </div>
  `;
  containerEl.appendChild(debateWrap);
}

function wireBadgeInteractions(sources, claimChecks) {
  const btnMode = document.getElementById('btn-badge-mode');
  const popoverMode = document.getElementById('popover-mode-details');
  const btnLang = document.getElementById('btn-badge-lang');
  const popoverLang = document.getElementById('popover-lang-menu');

  // Close helper
  const closeAllPopovers = () => {
    if (popoverMode) {
      popoverMode.classList.remove('open');
      if (btnMode) btnMode.setAttribute('aria-expanded', 'false');
    }
    if (popoverLang) {
      popoverLang.classList.remove('open');
      if (btnLang) btnLang.setAttribute('aria-expanded', 'false');
    }
  };

  if (btnMode && popoverMode) {
    btnMode.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = popoverMode.classList.contains('open');
      closeAllPopovers();
      if (!isOpen) {
        popoverMode.classList.add('open');
        btnMode.setAttribute('aria-expanded', 'true');
      }
    });
  }

  if (btnLang && popoverLang) {
    btnLang.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = popoverLang.classList.contains('open');
      closeAllPopovers();
      if (!isOpen) {
        popoverLang.classList.add('open');
        btnLang.setAttribute('aria-expanded', 'true');
      }
    });

    // Wire language selection items
    const langItems = popoverLang.querySelectorAll('.lang-menu-item');
    langItems.forEach(item => {
      item.addEventListener('click', async (e) => {
        e.stopPropagation();
        const targetLang = item.getAttribute('data-lang');
        closeAllPopovers();

        if (targetLang === 'auto' || targetLang === (currentRunMeta.language || 'en')) {
          // Revert to original
          if (currentTranslatedMarkdown) {
            currentTranslatedMarkdown = null;
            renderReport(originalMarkdown, sources, claimChecks, null, currentRunMeta);
            showToast('Showing original report', 'info');
          }
          return;
        }

        // Check translation cache first
        if (translationCache.has(targetLang)) {
          currentTranslatedMarkdown = translationCache.get(targetLang);
          const updatedMeta = { ...currentRunMeta, language: targetLang };
          renderReport(currentTranslatedMarkdown, sources, claimChecks, null, updatedMeta);
          showToast(`Report translated to ${targetLang.toUpperCase()}`, 'success');
          return;
        }

        // Show Skeleton while loading
        const reportProse = document.getElementById('report-prose');
        if (reportProse) {
          reportProse.innerHTML = `
            <div class="report-prose-skeleton">
              <div class="skeleton-line" style="width: 80%;"></div>
              <div class="skeleton-line" style="width: 100%;"></div>
              <div class="skeleton-line" style="width: 90%;"></div>
              <div class="skeleton-line" style="width: 95%;"></div>
              <div class="skeleton-line" style="width: 70%;"></div>
            </div>
          `;
        }

        // Call Translation API
        try {
          const runId = currentRunMeta.id || 'demo-ev-sample';
          const result = await api.translateReport(runId, targetLang);
          if (result && result.report) {
            translationCache.set(targetLang, result.report);
            currentTranslatedMarkdown = result.report;
            const updatedMeta = { ...currentRunMeta, language: targetLang };
            renderReport(result.report, sources, claimChecks, null, updatedMeta);
            showToast(`Report translated to ${result.language_name || targetLang.toUpperCase()}`, 'success');
          } else {
            throw new Error('Empty response from translation server');
          }
        } catch (err) {
          // Revert to original and display error toast
          currentTranslatedMarkdown = null;
          renderReport(originalMarkdown, sources, claimChecks, null, currentRunMeta);
          showToast(`Translation failed: ${err.message}`, 'error');
        }
      });
    });
  }

  // Click outside closes popovers
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#popover-mode-details') && !e.target.closest('#btn-badge-mode') &&
        !e.target.closest('#popover-lang-menu') && !e.target.closest('#btn-badge-lang')) {
      closeAllPopovers();
    }
  });

  // Esc closes popovers
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllPopovers();
    }
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.style.cssText = `
    padding: 10px 16px;
    background: var(--bg-surface-elevated, #1a2234);
    border: 1px solid ${type === 'error' ? 'var(--color-danger, #ef4444)' : 'var(--accent-primary, #7c83ff)'};
    color: var(--text-primary, #ffffff);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    font-size: 13px;
    margin-bottom: 8px;
    animation: fadeIn 200ms ease;
  `;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3500);
}

function prepareClaimHighlights(proseEl, claimChecks) {
  if (!proseEl || !claimChecks || claimChecks.length === 0) return;

  const paragraphs = proseEl.querySelectorAll('p, blockquote, li');
  paragraphs.forEach(p => {
    const chips = p.querySelectorAll('.citation-chip');
    chips.forEach(chip => {
      const citeId = parseInt(chip.getAttribute('data-cite'), 10);
      const claim = claimChecks.find(c => c.source_id === citeId);
      if (claim) {
        const isSupported = claim.verdict === 'supported';
        const wrapSpan = document.createElement('span');
        wrapSpan.className = `claim-sentence ${isSupported ? 'claim-verified' : 'claim-weak'}`;
        wrapSpan.title = isSupported ? 'Verified claim against source evidence' : 'Weak or disputed evidence';
        
        const prev = chip.previousSibling;
        if (prev && prev.nodeType === Node.TEXT_NODE && prev.textContent.trim().length > 10) {
          wrapSpan.textContent = prev.textContent;
          prev.parentNode.replaceChild(wrapSpan, prev);
        }
      }
    });
  });
}

function buildTableOfContents(proseEl) {
  const tocList = document.getElementById('toc-list');
  if (!tocList || !proseEl) return;
  tocList.innerHTML = '';

  const headings = proseEl.querySelectorAll('h2, h3');
  if (headings.length === 0) {
    tocList.innerHTML = '<li class="toc-empty">No section headings found.</li>';
    return;
  }

  headings.forEach((h, index) => {
    if (!h.id) {
      h.id = `report-section-${index}`;
    }
    const li = document.createElement('li');
    const levelClass = h.tagName.toLowerCase();
    li.className = `toc-item ${levelClass}`;
    
    const a = document.createElement('a');
    a.href = `#${h.id}`;
    a.textContent = h.textContent.replace(/^[#\s]+/, '').trim();
    
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.getElementById(h.id);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        tocList.querySelectorAll('.toc-item').forEach(it => it.classList.remove('active'));
        li.classList.add('active');
      }
    });

    li.appendChild(a);
    tocList.appendChild(li);
  });

  if (activeObserver) activeObserver.disconnect();

  const reportPanel = document.getElementById('panel-report');
  activeObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        tocList.querySelectorAll('.toc-item').forEach(item => {
          const link = item.querySelector('a');
          if (link && link.getAttribute('href') === `#${id}`) {
            item.classList.add('active');
          } else {
            item.classList.remove('active');
          }
        });
      }
    });
  }, {
    root: reportPanel,
    rootMargin: '-5% 0px -75% 0px',
    threshold: 0
  });

  headings.forEach(h => activeObserver.observe(h));
}

function setupCitationPopovers(proseEl, sourceMap, claimChecks) {
  let popover = document.getElementById('citation-popover');
  if (!popover) {
    popover = document.createElement('div');
    popover.id = 'citation-popover';
    popover.className = 'citation-popover';
    document.body.appendChild(popover);
  }

  const chips = proseEl.querySelectorAll('.citation-chip');
  chips.forEach(chip => {
    const citeId = parseInt(chip.getAttribute('data-cite'), 10);
    const source = sourceMap.get(citeId) || { domain: 'web source', url: '#', credibility: 'High', score: 85 };
    const claim = claimChecks.find(c => c.source_id === citeId || c.url === source.url);
    const credClass = (source.credibility || 'high').toLowerCase();

    const showPopover = () => {
      const rect = chip.getBoundingClientRect();
      popover.innerHTML = `
        <div class="popover-header">
          <div class="popover-domain-info">
            <span class="popover-cite-id">[${citeId}]</span>
            <span class="popover-domain">${escapeHtml(source.domain || 'Source')}</span>
          </div>
          <span class="badge badge-${credClass}">${source.credibility || 'Verified'}</span>
        </div>

        <div class="popover-title">${escapeHtml(source.title || source.url || 'Web source link')}</div>

        ${claim && claim.quote ? `
          <div class="popover-quote-box">
            <span class="quote-label">Exact Verified Quote:</span>
            "${escapeHtml(claim.quote)}"
          </div>
        ` : ''}

        <div class="popover-footer-hint">Click chip to view source card ↗</div>
      `;

      const popoverWidth = 320;
      let left = rect.left - 40;
      if (left + popoverWidth > window.innerWidth - 16) {
        left = window.innerWidth - popoverWidth - 16;
      }
      if (left < 16) left = 16;

      let top = rect.bottom + 8;
      if (top + 160 > window.innerHeight) {
        top = rect.top - 160;
      }

      popover.style.left = `${left}px`;
      popover.style.top = `${top}px`;
      popover.classList.add('visible');
    };

    const hidePopover = () => {
      popover.classList.remove('visible');
    };

    chip.addEventListener('mouseenter', showPopover);
    chip.addEventListener('focus', showPopover);
    chip.addEventListener('mouseleave', hidePopover);
    chip.addEventListener('blur', hidePopover);

    chip.addEventListener('click', (e) => {
      e.preventDefault();
      hidePopover();

      // Ensure side panel is open
      const panelReport = document.getElementById('panel-report');
      const sideCol = document.getElementById('report-col-side');
      const btnToggleSide = document.getElementById('btn-toggle-side-panel');
      if (panelReport) {
        panelReport.classList.remove('side-panel-collapsed');
        panelReport.classList.add('side-panel-active');
      }
      if (sideCol) sideCol.classList.add('side-open');
      if (btnToggleSide) btnToggleSide.setAttribute('aria-expanded', 'true');
      localStorage.setItem('rm_side_panel_state', 'open');

      switchSidePanelTab('sources');

      setTimeout(() => {
        const targetSource = document.getElementById(`source-card-${citeId}`);
        if (targetSource) {
          targetSource.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          targetSource.classList.add('highlight-pulse');
          setTimeout(() => targetSource.classList.remove('highlight-pulse'), 2400);
        }
      }, 50);
    });
  });
}

function wireReportToggles() {
  // Toggle: Highlight verified claims with keyboard accessibility (Space/Enter) and localStorage persistence
  const highlightToggle = document.getElementById('toggle-highlight-claims');
  const slider = highlightToggle?.parentElement?.querySelector('.switch-slider');
  const proseEl = document.getElementById('report-prose');

  const updateHighlightState = (isOn) => {
    if (proseEl) {
      if (isOn) {
        proseEl.classList.add('highlight-verified-claims');
      } else {
        proseEl.classList.remove('highlight-verified-claims');
      }
    }
    localStorage.setItem('rm_highlight_verified_claims', isOn ? 'true' : 'false');
    if (slider) slider.setAttribute('aria-checked', isOn ? 'true' : 'false');
  };

  if (highlightToggle) {
    highlightToggle.addEventListener('change', (e) => {
      updateHighlightState(e.target.checked);
    });
  }

  if (slider && highlightToggle) {
    slider.addEventListener('keydown', (e) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        highlightToggle.checked = !highlightToggle.checked;
        highlightToggle.dispatchEvent(new Event('change'));
      }
    });
  }

  // Toggle button for side panel ("Evidence" button)
  const btnToggleSide = document.getElementById('btn-toggle-side-panel');
  const btnCloseSide = document.getElementById('btn-close-side-panel');
  const sideCol = document.getElementById('report-col-side');
  const panelReport = document.getElementById('panel-report');

  const toggleEvidenceSidePanel = () => {
    if (!panelReport) return;
    const isCurrentlyCollapsed = panelReport.classList.contains('side-panel-collapsed');
    
    if (isCurrentlyCollapsed) {
      panelReport.classList.remove('side-panel-collapsed');
      panelReport.classList.add('side-panel-active');
      if (sideCol) sideCol.classList.add('side-open');
      if (btnToggleSide) btnToggleSide.setAttribute('aria-expanded', 'true');
      localStorage.setItem('rm_side_panel_state', 'open');
    } else {
      panelReport.classList.add('side-panel-collapsed');
      panelReport.classList.remove('side-panel-active');
      if (sideCol) sideCol.classList.remove('side-open');
      if (btnToggleSide) btnToggleSide.setAttribute('aria-expanded', 'false');
      localStorage.setItem('rm_side_panel_state', 'closed');
    }
  };

  if (btnToggleSide) {
    btnToggleSide.addEventListener('click', toggleEvidenceSidePanel);
  }

  if (btnCloseSide) {
    btnCloseSide.addEventListener('click', toggleEvidenceSidePanel);
  }

  // Side Panel Tab Buttons
  const tabBtns = document.querySelectorAll('.side-tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-side-tab');
      switchSidePanelTab(targetTab);
    });
  });
}

export function switchSidePanelTab(tabName) {
  const tabBtns = document.querySelectorAll('.side-tab-btn');
  tabBtns.forEach(btn => {
    const isTarget = btn.getAttribute('data-side-tab') === tabName;
    btn.classList.toggle('active', isTarget);
  });

  const paneSources = document.getElementById('tab-sources-content');
  const paneConflicts = document.getElementById('tab-conflicts-content');
  const paneVerification = document.getElementById('tab-verification-content');

  if (paneSources) paneSources.style.display = tabName === 'sources' ? 'block' : 'none';
  if (paneConflicts) paneConflicts.style.display = tabName === 'contradictions' ? 'block' : 'none';
  if (paneVerification) paneVerification.style.display = tabName === 'verification' ? 'block' : 'none';
}

function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
