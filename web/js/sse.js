// Server-Sent Events (SSE) Client with Auto-reconnect & Event handling
export class SSEClient {
  constructor(runId, onEvent, onDone, onError) {
    this.runId = runId;
    this.onEvent = onEvent;
    this.onDone = onDone;
    this.onError = onError;
    this.eventSource = null;
    this.lastEventId = 0;
    this.retryCount = 0;
    this.maxRetries = 5;
    this.isClosed = false;
  }

  connect() {
    if (this.isClosed) return;
    const url = `/api/research/${this.runId}/stream?from=${this.lastEventId}`;
    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (e) => {
      this.retryCount = 0;
      try {
        const data = JSON.parse(e.data);
        if (e.lastEventId) {
          this.lastEventId = parseInt(e.lastEventId, 10) + 1;
        }
        if (this.onEvent) this.onEvent(data);

        if (data.kind === 'end' || ['done', 'error', 'cancelled'].includes(data.status)) {
          this.close();
          if (this.onDone) this.onDone(data);
        }
      } catch (err) {
        console.error('SSE JSON parse error:', err, e.data);
      }
    };

    this.eventSource.onerror = (err) => {
      console.warn('SSE connection warning:', err);
      this.eventSource.close();
      if (this.isClosed) return;

      if (this.retryCount < this.maxRetries) {
        this.retryCount++;
        const backoff = Math.min(1000 * Math.pow(2, this.retryCount), 10000);
        setTimeout(() => this.connect(), backoff);
      } else {
        if (this.onError) this.onError(new Error('Connection lost after multiple retries'));
      }
    };
  }

  close() {
    this.isClosed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
