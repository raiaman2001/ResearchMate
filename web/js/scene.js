// Three.js WebGL background and CSS3DRenderer Scene Manager
import { CameraManager } from './camera.js';

let THREE = null;
let CSS3DRenderer = null;
let CSS3DObject = null;

export class Scene3D {
  constructor() {
    this.glRenderer = null;
    this.cssRenderer = null;
    this.sceneGL = null;
    this.sceneCSS = null;
    this.camera = null;
    this.cameraManager = null;
    this.particles = null;
    this.globe = null;
    this.agentNodes = [];
    this.activeAgentIdx = -1;
    this.isPaused = false;
    this.cssObjects = new Map();
  }

  async init(canvasEl, cssContainerEl) {
    try {
      // Pinned CDN Three.js and CSS3DRenderer
      if (!window.THREE) {
        await import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js').then(m => {
          window.THREE = m;
        });
        const cssMod = await import('https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/renderers/CSS3DRenderer.js');
        CSS3DRenderer = cssMod.CSS3DRenderer;
        CSS3DObject = cssMod.CSS3DObject;
      }
      THREE = window.THREE;

      const width = window.innerWidth;
      const height = window.innerHeight;

      // Shared Perspective Camera (initial idle pose z = 840)
      this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 5000);
      this.camera.position.set(0, 0, 840);
      this.cameraManager = new CameraManager(this.camera);

      // 1. WebGL Background Layer
      this.sceneGL = new THREE.Scene();
      this.glRenderer = new THREE.WebGLRenderer({ canvas: canvasEl, alpha: true, antialias: true });
      this.glRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      this.glRenderer.setSize(width, height);

      this.createStarfield();
      this.createNeuralGlobe();

      // 2. CSS3D DOM Layer
      this.sceneCSS = new THREE.Scene();
      this.cssRenderer = new CSS3DRenderer();
      this.cssRenderer.setSize(width, height);
      this.cssRenderer.domElement.style.position = 'absolute';
      this.cssRenderer.domElement.style.top = '0';
      this.cssRenderer.domElement.style.left = '0';
      cssContainerEl.appendChild(this.cssRenderer.domElement);

      // Register DOM panels
      this.registerPanels();

      // Initial centralized view visibility state (Deck view)
      this.setView('idle');

      // Set initial centered layout for globe below header
      this.updateGlobeLayout();

      // Resize and Visibility listeners
      window.addEventListener('resize', () => this.onResize());
      document.addEventListener('visibilitychange', () => {
        this.isPaused = document.hidden;
      });

      this.animate();
    } catch (err) {
      console.warn('3D WebGL / CSS3D init failed, activating Flat Mode fallback:', err);
      document.body.classList.add('mode-flat');
      this.isFlatMode = true;
    }
  }

  createStarfield() {
    const count = 1200; // <= 1500 particles
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 2400;
      positions[i + 1] = (Math.random() - 0.5) * 2400;
      positions[i + 2] = (Math.random() - 0.5) * 2000 - 400;
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
      color: 0x7C83FF,
      size: 2.2,
      transparent: true,
      opacity: 0.6
    });
    this.particles = new THREE.Points(geometry, material);
    this.sceneGL.add(this.particles);
  }

  createNeuralGlobe() {
    const globeGroup = new THREE.Group();
    // Use unit geometry (radius: 100), then scale accurately to fit viewport
    const geometry = new THREE.SphereGeometry(100, 32, 32);
    const wireframe = new THREE.WireframeGeometry(geometry);
    const line = new THREE.LineSegments(wireframe);
    line.material.color = new THREE.Color(0x14B8A6);
    line.material.transparent = true;
    line.material.opacity = 0.65;
    globeGroup.add(line);
    this.globeWireframe = line;

    // Glowing network vertices
    const ptsGeo = new THREE.BufferGeometry();
    const posArr = geometry.attributes.position.array;
    ptsGeo.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
    const ptsMat = new THREE.PointsMaterial({
      color: 0x7C83FF,
      size: 3.5,
      transparent: true,
      opacity: 0.75
    });
    const pts = new THREE.Points(ptsGeo, ptsMat);
    globeGroup.add(pts);
    this.globePoints = pts;

    this.globe = globeGroup;
    this.sceneGL.add(this.globe);
    this.createAgentPipeline();
  }

  updateGlobeLayout() {
    if (!this.globe || !this.camera) return;
    const headerHeight = 56;
    const windowH = window.innerHeight;
    const visibleH = windowH - headerHeight;

    // Viewport center Y in screen pixels: headerHeight + visibleH / 2
    // Screen coords to 3D NDC: shift upwards by ~30px so bottom text has clear separation
    const screenCenterY = (headerHeight + visibleH / 2) - 30;
    const ndcCenterY = 1 - (2 * screenCenterY / windowH);

    // Compute 3D world Y at globe depth (z = 0 relative to camera at z = 840)
    const distToCamera = 840; // match camera.position.z in idle
    const vFovRad = (this.camera.fov * Math.PI) / 180;
    const visibleWorldH = 2 * Math.tan(vFovRad / 2) * distToCamera;
    const centerYWorld = (ndcCenterY * visibleWorldH) / 2;

    // Globe diameter: scaled to 78% of visible height to leave clean breathing room around header, cards & caption
    const visibleAreaWorldH = (visibleH / windowH) * visibleWorldH;
    const targetDiameter = visibleAreaWorldH * 0.78;
    const targetRadius = targetDiameter / 2;
    const scale = targetRadius / 100;

    this.globe.scale.set(scale, scale, scale);
    this.globe.position.set(0, centerYWorld, this.isGlobeDimmed ? -120 : 0);
    this.globeCenterY = centerYWorld;
  }

  setGlobeDimmed(isDimmed) {
    this.isGlobeDimmed = isDimmed;
    if (this.globeWireframe) {
      this.globeWireframe.material.opacity = isDimmed ? 0.35 : 0.65;
    }
    if (this.globePoints) {
      this.globePoints.material.opacity = isDimmed ? 0.40 : 0.75;
    }
    if (this.globe && this.globeCenterY !== undefined) {
      this.globe.position.z = isDimmed ? -120 : 0;
    }
  }

  createAgentPipeline() {
    // Pipeline wave visual removed per user request
    this.agentNodes = [];
  }

  triggerAgentActive(agentName) {
    // No-op since pipeline curve is removed
  }

  animateDataPacket() {
    // No-op
  }

  registerPanels() {
    const panels = [
      { id: 'panel-composer', pos: [0, 0, 0], rot: [0, 0, 0] },
      { id: 'panel-history', pos: [-530, 10, -20], rot: [0, 0.08, 0] },
      { id: 'panel-telemetry', pos: [530, 10, -20], rot: [0, -0.08, 0] },
      { id: 'panel-trace', pos: [0, 0, 2000], rot: [0, 0, 0] },
      { id: 'panel-report', pos: [0, -100, 3000], rot: [0, 0, 0] }
    ];

    panels.forEach(p => {
      const el = document.getElementById(p.id);
      if (el && CSS3DObject) {
        const obj = new CSS3DObject(el);
        obj.position.set(...p.pos);
        obj.rotation.set(...p.rot);
        this.sceneCSS.add(obj);
        this.cssObjects.set(p.id, obj);
      }
    });
  }

  // Centralized View Switching (Requirement 2 & 3)
  setView(viewName) {
    this.currentView = viewName;

    const VIEW_PANELS = {
      idle: ['panel-composer', 'panel-history', 'panel-telemetry'],
      plan: ['panel-composer'],
      running: ['panel-trace'],
      report: ['panel-report'],
      graph: []
    };

    const activeIds = VIEW_PANELS[viewName] || [];
    const allPanelIds = ['panel-composer', 'panel-history', 'panel-telemetry', 'panel-trace', 'panel-report'];

    allPanelIds.forEach(id => {
      const el = document.getElementById(id);
      const obj = this.cssObjects.get(id);
      const isActive = activeIds.includes(id);

      if (isActive) {
        if (viewName === 'idle') {
          const isHidden = el && el.classList.contains('panel-idle-hidden');
          if (el) {
            el.style.display = isHidden ? 'none' : 'flex';
            el.style.pointerEvents = isHidden ? 'none' : 'auto';
          }
          if (obj) obj.visible = !isHidden;
        } else if (id === 'panel-report') {
          if (el) {
            el.style.display = 'block';
            el.style.pointerEvents = 'auto';
            el.style.opacity = '1';
            el.style.visibility = 'visible';
          }
          if (obj) obj.visible = true;
        } else {
          if (el) {
            el.style.display = 'flex';
            el.style.pointerEvents = 'auto';
            el.style.opacity = '1';
            el.style.visibility = 'visible';
          }
          if (obj) obj.visible = true;
        }
      } else {
        // Requirement 2: For every view other than active, sets CSS3DObject.visible = false AND element.style.display = 'none' AND pointer-events none
        if (el) {
          el.style.display = 'none';
          el.style.pointerEvents = 'none';
        }
        if (obj) obj.visible = false;
      }
    });

    // Requirement 2: Also hide the WebGL agent nodes/connectors/packets of the Running view
    const isRunning = (viewName === 'running');
    if (this.agentNodes) {
      this.agentNodes.forEach(node => {
        if (node.mesh) node.mesh.visible = isRunning;
        if (node.halo) node.halo.visible = isRunning;
      });
    }
    if (this.pipelineCurve) {
      this.pipelineCurve.visible = isRunning;
    }
    if (this.packetMesh) {
      this.packetMesh.visible = isRunning;
    }

    // Requirement 3: Caption show only in Deck view (display: none in all others)
    const idleCaption = document.getElementById('globe-idle-caption');
    const floatingLeft = document.getElementById('floating-cards-left');
    const floatingRight = document.getElementById('floating-cards-right');

    if (viewName === 'idle') {
      const composer = document.getElementById('panel-composer');
      const isPanelsVisible = composer && !composer.classList.contains('panel-idle-hidden');
      if (idleCaption) {
        idleCaption.style.display = isPanelsVisible ? 'none' : 'block';
      }
      if (floatingLeft) floatingLeft.classList.toggle('hidden', isPanelsVisible);
      if (floatingRight) floatingRight.classList.toggle('hidden', isPanelsVisible);
    } else {
      if (idleCaption) idleCaption.style.setProperty('display', 'none', 'important');
      if (floatingLeft) floatingLeft.classList.add('hidden');
      if (floatingRight) floatingRight.classList.add('hidden');
    }

    // Toggle export buttons group in header: visible only in Report view
    const exportGroup = document.getElementById('report-export-group');
    if (exportGroup) {
      exportGroup.style.display = (viewName === 'report') ? 'flex' : 'none';
    }

    // Body class for CSS scoping
    document.body.classList.remove('view-idle', 'view-plan', 'view-running', 'view-report', 'view-graph');
    document.body.classList.add(`view-${viewName}`);
  }

  onResize() {
    if (!this.camera) return;
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (this.glRenderer) this.glRenderer.setSize(w, h);
    if (this.cssRenderer) this.cssRenderer.setSize(w, h);
    this.updateGlobeLayout();

    if (document.body.classList.contains('view-report')) {
      const fovFactor = (h * 0.5) / Math.tan((45 * 0.5 * Math.PI) / 180);
      this.camera.position.set(0, -100, 3000 + fovFactor);
    }
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    if (this.isPaused) return;

    if (this.particles) this.particles.rotation.y += 0.0003;
    if (this.globe) this.globe.rotation.y += 0.001;

    // Animate active agent node pulse
    if (this.activeAgentIdx >= 0 && this.agentNodes[this.activeAgentIdx]) {
      const activeNode = this.agentNodes[this.activeAgentIdx];
      const pulse = 1 + Math.sin(performance.now() * 0.008) * 0.15;
      activeNode.halo.scale.set(pulse * 1.5, pulse * 1.5, pulse * 1.5);
    }

    // Animate data packet along pipeline curve
    if (this.isPacketAnimating && this.pipelineSpline && this.packetMesh) {
      this.packetProgress += 0.015;
      if (this.packetProgress <= 1.0) {
        const pt = this.pipelineSpline.getPoint(this.packetProgress);
        this.packetMesh.position.copy(pt);
      } else {
        this.isPacketAnimating = false;
        this.packetMesh.visible = false;
      }
    }

    if (this.cameraManager) this.cameraManager.update();

    if (this.glRenderer && this.sceneGL) this.glRenderer.render(this.sceneGL, this.camera);
    if (this.cssRenderer && this.sceneCSS) this.cssRenderer.render(this.sceneCSS, this.camera);
  }
}

export const scene3D = new Scene3D();
