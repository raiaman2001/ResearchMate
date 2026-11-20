// Global Application State Manager
class StateManager extends EventTarget {
  constructor() {
    super();
    this.state = {
      theme: localStorage.getItem('rm_theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'),
      activeView: 'composer', // 'composer' | 'running' | 'result'
      activeTab: 'report',    // 'report' | 'sources' | 'conflicts' | 'debate' | 'graph' | 'verification'
      currentRunId: null,
      currentRun: null,       // { id, topic, status, pending, result, events: [] }
      events: [],
      sources: [],
      claims: [],
      conflicts: [],
      history: [],
      documents: [],
      kgData: null,
      statsDrawerOpen: true,
      sidebarCollapsed: localStorage.getItem('rm_sidebar_collapsed') === 'true',
      isDemo: new URLSearchParams(window.location.search).get('demo') === '1'
    };
  }

  get() {
    return this.state;
  }

  set(partial) {
    this.state = { ...this.state, ...partial };
    this.dispatchEvent(new CustomEvent('change', { detail: this.state }));
  }

  toggleSidebar() {
    const next = !this.state.sidebarCollapsed;
    localStorage.setItem('rm_sidebar_collapsed', next.toString());
    this.set({ sidebarCollapsed: next });
    return next;
  }

  toggleTheme() {
    const next = this.state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('rm_theme', next);
    document.documentElement.setAttribute('data-theme', next);
    this.set({ theme: next });
  }

  addEvent(event) {
    const events = [...this.state.events, event];
    this.set({ events });
    this.dispatchEvent(new CustomEvent('event', { detail: event }));
  }

  clearEvents() {
    this.set({ events: [] });
  }
}

export const state = new StateManager();
