// Side Panel Content Population Module
// Sources | Contradictions | Verification | Debate

export function renderSourcesList(sources, containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';

  const countBadge = document.getElementById('count-sources');
  if (countBadge) {
    countBadge.textContent = sources ? sources.length : 0;
  }

  if (!sources || sources.length === 0) {
    containerEl.innerHTML = '<div class="side-panel-empty-state">No sources recorded for this research.</div>';
    return;
  }

  const list = document.createElement('div');
  list.className = 'side-sources-list';

  sources.forEach((s, idx) => {
    const id = s.id || (idx + 1);
    let domain = s.domain;
    if (!domain && s.url) {
      try { domain = new URL(s.url).hostname; } catch (e) { domain = 'web source'; }
    }
    if (!domain) domain = 'web source';

    const url = s.url || '#';
    const title = s.title || domain;
    const cred = s.credibility || (s.score >= 80 ? 'High' : s.score >= 50 ? 'Medium' : 'Low');
    const credClass = cred.toLowerCase();
    const score = s.score !== undefined ? s.score : (credClass === 'high' ? 90 : credClass === 'medium' ? 65 : 40);
    const isOpened = s.opened !== false;

    const card = document.createElement('div');
    card.className = 'source-card';
    card.id = `source-card-${id}`;
    card.innerHTML = `
      <div class="source-card-header">
        <div class="source-domain-info">
          <span class="source-favicon-wrapper">
            <svg class="source-fallback-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            <img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${domain}&sz=32" alt="" onload="this.classList.add('loaded')" onerror="this.remove()">
          </span>
          <span class="source-id">[${id}]</span>
          <span class="source-domain" title="${escapeHtml(domain)}">${escapeHtml(domain)}</span>
        </div>
        <span class="badge badge-${credClass}">${escapeHtml(cred)}</span>
      </div>

      <a class="source-title" href="${url}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(title)}">
        ${escapeHtml(title)}
      </a>

      <a class="source-url-text" href="${url}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(url)}">
        ${escapeHtml(url)}
      </a>

      <div class="source-score-row">
        <div class="source-score-bar-bg" title="Credibility score: ${score}/100">
          <div class="source-score-bar-fill ${credClass}" style="width: ${Math.min(100, Math.max(5, score))}%;"></div>
        </div>
        <span class="source-score-label">${score}/100</span>
      </div>

      <div class="source-card-footer">
        ${isOpened ? '<span class="source-opened-tag">opened by agent</span>' : '<span style="flex:1;"></span>'}
        <a href="${url}" target="_blank" rel="noopener noreferrer" class="source-link-out">
          Open ↗
        </a>
      </div>
    `;
    list.appendChild(card);
  });

  containerEl.appendChild(list);
}

export function renderConflictsList(conflicts, containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';

  const countBadge = document.getElementById('count-contradictions');
  if (countBadge) {
    countBadge.textContent = conflicts ? conflicts.length : 0;
  }

  if (!conflicts || conflicts.length === 0) {
    containerEl.innerHTML = '<div class="side-panel-empty-state">No contradictions found</div>';
    return;
  }

  const list = document.createElement('div');
  list.className = 'side-conflicts-list';

  conflicts.forEach(c => {
    const severity = c.severity || 'Moderate';
    const severityClass = severity.toLowerCase();

    const card = document.createElement('div');
    card.className = 'conflict-card';
    card.innerHTML = `
      <div class="conflict-card-header">
        <span class="conflict-topic-title">⚖️ ${escapeHtml(c.topic || 'Claim Discrepancy')}</span>
        <span class="badge badge-${severityClass}">${severity}</span>
      </div>

      <div class="conflict-comparison-grid">
        <div class="conflict-claim-side claim-side-a">
          <div class="conflict-source-label">${escapeHtml(c.source_a || 'Source A')} claims:</div>
          <div class="conflict-quote">"${escapeHtml(c.claim_a || '')}"</div>
        </div>

        <div class="conflict-claim-side claim-side-b">
          <div class="conflict-source-label">${escapeHtml(c.source_b || 'Source B')} claims:</div>
          <div class="conflict-quote">"${escapeHtml(c.claim_b || '')}"</div>
        </div>
      </div>

      ${c.explanation ? `
        <div class="conflict-explanation">
          <strong>Analysis:</strong> ${escapeHtml(c.explanation)}
        </div>
      ` : ''}
    `;
    list.appendChild(card);
  });

  containerEl.appendChild(list);
}

export function renderVerificationList(claims, containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';

  const countBadge = document.getElementById('count-verification');
  if (countBadge) {
    countBadge.textContent = claims ? claims.length : 0;
  }

  if (!claims || claims.length === 0) {
    containerEl.innerHTML = '<div class="side-panel-empty-state">No claim verification checks recorded.</div>';
    return;
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'verification-table-wrapper';

  const table = document.createElement('table');
  table.className = 'verification-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th style="min-width:140px;">Claim</th>
        <th style="width:70px;">Source</th>
        <th style="min-width:150px;">Exact Quote</th>
        <th style="width:80px;">Status</th>
        <th style="width:60px;">Retries</th>
      </tr>
    </thead>
    <tbody>
      ${claims.map(c => {
        const isVerified = c.verdict === 'supported';
        const statusBadge = isVerified ? 'Verified' : 'Failed';
        const badgeClass = isVerified ? 'badge-high' : 'badge-low';
        const retries = c.retry !== undefined ? c.retry : (c.retries !== undefined ? c.retries : 0);
        const sourceLabel = c.source_id ? `[${c.source_id}]` : (c.domain || 'Source');

        return `
          <tr>
            <td class="col-claim">${escapeHtml(c.claim || '—')}</td>
            <td class="col-source">
              <a href="${c.url || '#'}" target="_blank" rel="noopener noreferrer">${sourceLabel}</a>
            </td>
            <td class="col-quote">
              <span class="quote-text">${c.quote ? `"${escapeHtml(c.quote)}"` : '—'}</span>
            </td>
            <td class="col-status">
              <span class="badge ${badgeClass}">${statusBadge}</span>
            </td>
            <td class="col-retries numeric-cell">${retries}</td>
          </tr>
        `;
      }).join('')}
    </tbody>
  `;

  wrapper.appendChild(table);
  containerEl.appendChild(wrapper);
}

export function renderDebateView(debateData, containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';
  const proPoints = (debateData && debateData.pro) || [];
  const conPoints = (debateData && debateData.con) || [];
  const verdict = (debateData && debateData.verdict) || 'Balanced Evidence Assessment';

  const debateWrap = document.createElement('div');
  debateWrap.className = 'debate-view-container';
  debateWrap.innerHTML = `
    <div class="debate-verdict-banner">
      <div class="verdict-label">SYNTHESIZED CONSENSUS VERDICT</div>
      <div class="verdict-text">${escapeHtml(verdict)}</div>
    </div>
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
  `;
  containerEl.appendChild(debateWrap);
}

function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
