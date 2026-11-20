// Interactive Knowledge Graph Visualizer using D3 / SVG
export function renderKnowledgeGraph(graphData, containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';

  const nodes = (graphData && graphData.nodes) || [];
  const edges = (graphData && graphData.edges) || [];

  if (nodes.length === 0) {
    containerEl.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:320px; color:var(--text-muted); gap:12px;">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
        <div>Knowledge Graph is currently empty. Run research with Memory enabled to accumulate entity relations.</div>
      </div>
    `;
    return;
  }

  const width = containerEl.clientWidth || 800;
  const height = 450;

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', `${height}`);
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.style.borderRadius = 'var(--radius-md)';
  svg.style.background = 'var(--bg-surface-elevated)';

  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  svg.appendChild(g);

  // Position nodes radially
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.35;

  const nodeMap = new Map();
  nodes.forEach((node, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    nodeMap.set(node.id, { ...node, x, y });
  });

  // Render edges
  edges.forEach(edge => {
    const s = nodeMap.get(edge.source);
    const t = nodeMap.get(edge.target);
    if (!s || !t) return;

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', `${s.x}`);
    line.setAttribute('y1', `${s.y}`);
    line.setAttribute('x2', `${t.x}`);
    line.setAttribute('y2', `${t.y}`);
    line.setAttribute('stroke', 'var(--border-hover)');
    line.setAttribute('stroke-width', '1.5');
    line.setAttribute('stroke-dasharray', '3,3');
    g.appendChild(line);

    // Relation label
    if (edge.relation) {
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', `${(s.x + t.x) / 2}`);
      text.setAttribute('y', `${(s.y + t.y) / 2 - 4}`);
      text.setAttribute('fill', 'var(--text-muted)');
      text.setAttribute('font-size', '10px');
      text.setAttribute('text-anchor', 'middle');
      text.textContent = edge.relation;
      g.appendChild(text);
    }
  });

  // Render node circles and labels
  nodeMap.forEach(node => {
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.style.cursor = 'pointer';

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', `${node.x}`);
    circle.setAttribute('cy', `${node.y}`);
    circle.setAttribute('r', '16');
    circle.setAttribute('fill', 'var(--accent-primary)');
    circle.setAttribute('stroke', 'var(--bg-surface)');
    circle.setAttribute('stroke-width', '2');

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', `${node.x}`);
    text.setAttribute('y', `${node.y + 28}`);
    text.setAttribute('fill', 'var(--text-primary)');
    text.setAttribute('font-size', '12px');
    text.setAttribute('font-weight', '500');
    text.setAttribute('text-anchor', 'middle');
    text.textContent = node.label || node.id;

    group.appendChild(circle);
    group.appendChild(text);

    group.addEventListener('click', () => {
      alert(`Entity: ${node.label || node.id}\nType: ${node.type || 'Concept'}`);
    });

    g.appendChild(group);
  });

  containerEl.appendChild(svg);
}
