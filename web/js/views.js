// 3D View Camera Poses & Transitions
import { scene3D } from './scene.js';

export const POSES = {
  idle: {
    pos: { x: 0, y: 0, z: 840 },
    rot: { x: 0, y: 0, z: 0 },
    duration: 1000,
    parallax: true
  },
  plan: {
    pos: { x: 0, y: 0, z: 650 },
    rot: { x: 0.05, y: 0, z: 0 },
    duration: 800,
    parallax: false
  },
  running: {
    pos: { x: 0, y: -40, z: 2850 },
    rot: { x: 0, y: 0, z: 0 },
    duration: 1100,
    parallax: true
  },
  report: {
    pos: { x: 0, y: -100, z: 3950 },
    rot: { x: 0, y: 0, z: 0 }, // tilt 0
    duration: 1000,
    parallax: false // no parallax while reading/scrolling
  },
  graph: {
    pos: { x: 0, y: 0, z: 1200 },
    rot: { x: 0.1, y: 0.15, z: 0 },
    duration: 1000,
    parallax: true
  }
};

export class ViewManager {
  constructor() {
    this.currentView = 'idle';
  }

  goTo(viewName) {
    const pose = POSES[viewName];
    if (!pose) return;
    this.currentView = viewName;

    // Centralized view switching (Requirement 2 & 3)
    if (scene3D && typeof scene3D.setView === 'function') {
      scene3D.setView(viewName);
    }

    // Dynamic 1:1 camera distance calculation for report view to ensure 100% pixel matching
    let targetPos = { ...pose.pos };
    let targetRot = { ...pose.rot };
    if (viewName === 'report') {
      const fovFactor = (window.innerHeight * 0.5) / Math.tan((45 * 0.5 * Math.PI) / 180);
      targetPos = { x: 0, y: -100, z: 3000 + fovFactor };
      targetRot = { x: 0, y: 0, z: 0 };

      // Requirement 1: Scroll container starts at scrollTop 0 on every open
      const panelReport = document.getElementById('panel-report');
      if (panelReport) {
        panelReport.scrollTop = 0;
      }
    }

    if (scene3D.cameraManager) {
      scene3D.cameraManager.allowParallax = pose.parallax;
      scene3D.cameraManager.flyTo(targetPos, targetRot, pose.duration);
    }
  }
}

export const viewManager = new ViewManager();
if (typeof window !== 'undefined') {
  window.viewManager = viewManager;
  window.setView = (name) => viewManager.goTo(name);
}
