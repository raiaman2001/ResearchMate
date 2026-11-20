// Smooth Camera Pose Flight Manager
export class CameraManager {
  constructor(camera) {
    this.camera = camera;
    this.targetPos = { x: 0, y: 0, z: 840 };
    this.targetRot = { x: 0, y: 0, z: 0 };
    this.isFlying = false;
    this.flightStart = 0;
    this.flightDuration = 1000;
    this.startPos = { x: 0, y: 0, z: 840 };
    this.startRot = { x: 0, y: 0, z: 0 };

    this.mouse = { x: 0, y: 0 };
    this.parallax = { x: 0, y: 0 };
    this.allowParallax = true;

    window.addEventListener('mousemove', (e) => {
      this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    });
  }

  flyTo(pos, rot, duration = 1000) {
    this.startPos = { ...this.camera.position };
    this.startRot = { x: this.camera.rotation.x, y: this.camera.rotation.y, z: this.camera.rotation.z };
    this.targetPos = { ...pos };
    this.targetRot = { ...rot };
    this.flightDuration = duration;
    this.flightStart = performance.now();
    this.isFlying = true;
  }

  update() {
    if (this.isFlying) {
      const now = performance.now();
      const progress = Math.min((now - this.flightStart) / this.flightDuration, 1.0);
      // EaseInOutCubic
      const t = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

      this.camera.position.x = this.startPos.x + (this.targetPos.x - this.startPos.x) * t;
      this.camera.position.y = this.startPos.y + (this.targetPos.y - this.startPos.y) * t;
      this.camera.position.z = this.startPos.z + (this.targetPos.z - this.startPos.z) * t;

      this.camera.rotation.x = this.startRot.x + (this.targetRot.x - this.startRot.x) * t;
      this.camera.rotation.y = this.startRot.y + (this.targetRot.y - this.startRot.y) * t;
      this.camera.rotation.z = this.startRot.z + (this.targetRot.z - this.startRot.z) * t;

      if (progress >= 1.0) {
        this.isFlying = false;
      }
    } else if (this.allowParallax) {
      // Gentle parallax (max ~3-4 deg)
      const targetParallaxX = this.mouse.x * 25;
      const targetParallaxY = this.mouse.y * 18;
      this.parallax.x += (targetParallaxX - this.parallax.x) * 0.05;
      this.parallax.y += (targetParallaxY - this.parallax.y) * 0.05;

      this.camera.position.x = this.targetPos.x + this.parallax.x;
      this.camera.position.y = this.targetPos.y + this.parallax.y;
    }
  }
}
