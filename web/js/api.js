// REST API Client for ResearchMate Backend
const API_BASE = '/api';

export const api = {
  async preScrape(query) {
    const res = await fetch(`${API_BASE}/research/pre-scrape`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Pre-scrape failed');
    return res.json();
  },

  async startResearch(payload) {
    const res = await fetch(`${API_BASE}/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed to start research');
    return res.json();
  },

  async getResearch(id) {
    const res = await fetch(`${API_BASE}/research/${id}`);
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed to load research');
    return res.json();
  },

  async approvePlan(id, subQuestions, debatePlan = null) {
    const res = await fetch(`${API_BASE}/research/${id}/plan/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: true, sub_questions: subQuestions, debate_plan: debatePlan })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed to approve plan');
    return res.json();
  },

  async cancelResearch(id) {
    const res = await fetch(`${API_BASE}/research/${id}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to cancel research');
    return res.json();
  },

  async getHistory() {
    const res = await fetch(`${API_BASE}/history?limit=50`);
    if (!res.ok) return [];
    return res.json();
  },

  async getHistoryDetail(dbId) {
    const res = await fetch(`${API_BASE}/history/${dbId}`);
    if (!res.ok) throw new Error('Historical item not found');
    return res.json();
  },

  async getDocuments() {
    const res = await fetch(`${API_BASE}/documents`);
    if (!res.ok) return [];
    return res.json();
  },

  async uploadDocument(file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/documents`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed to upload PDF');
    return res.json();
  },

  async deleteDocument(docId) {
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete document');
    return res.json();
  },

  async getKnowledgeGraph() {
    const res = await fetch(`${API_BASE}/memory/graph`);
    if (!res.ok) return { nodes: [], edges: [] };
    return res.json();
  },

  async getDemoFixture() {
    const res = await fetch(`${API_BASE}/demo/fixture`);
    if (!res.ok) throw new Error('Failed to load demo fixture');
    return res.json();
  },

  async translateReport(id, language) {
    const res = await fetch(`${API_BASE}/research/${id}/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Translation endpoint unavailable' }));
      throw new Error(err.detail || 'Translation failed');
    }
    return res.json();
  },

  getExportUrl(id, format) {
    return `${API_BASE}/research/${id}/export?format=${format}`;
  },

  async exportRawDossier(markdown, title, format = 'pdf') {
    const res = await fetch(`${API_BASE}/research/export-raw`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown, title, format })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Export failed' }));
      throw new Error(err.detail || 'Export failed');
    }
    return res.blob();
  }
};
