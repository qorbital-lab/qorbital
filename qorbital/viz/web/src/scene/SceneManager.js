import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export class SceneManager {
  /**
   * @param {HTMLCanvasElement} canvas
   */
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0a12);

    this.camera = new THREE.PerspectiveCamera(
      50,
      1,
      0.01,
      500,
    );
    this.camera.position.set(4, 2, 5);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, 0, 0);

    const ambient = new THREE.AmbientLight(0xffffff, 0.45);
    this.scene.add(ambient);
    const key = new THREE.DirectionalLight(0xffffff, 1.0);
    key.position.set(5, 8, 6);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0x8899cc, 0.35);
    fill.position.set(-4, -2, -3);
    this.scene.add(fill);

    this.contentRoot = new THREE.Group();
    this.scene.add(this.contentRoot);

    this._animationFrame = 0;
    this._onResize = () => this.resize();
    this._resizeObserver = null;
    window.addEventListener("resize", this._onResize);
    const parent = this.canvas.parentElement;
    if (parent && "ResizeObserver" in window) {
      this._resizeObserver = new ResizeObserver(() => this.resize());
      this._resizeObserver.observe(parent);
    }
    this.resize();
    this._animate = this._animate.bind(this);
    this._animationFrame = requestAnimationFrame(this._animate);
  }

  resize() {
    const parent = this.canvas.parentElement;
    if (!parent) return;
    const width = parent.clientWidth;
    const height = parent.clientHeight;
    if (width === 0 || height === 0) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  _animate() {
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this._animationFrame = requestAnimationFrame(this._animate);
  }

  /**
   * @param {THREE.Object3D} object
   */
  setContent(object) {
    while (this.contentRoot.children.length > 0) {
      const child = this.contentRoot.children[0];
      this.contentRoot.remove(child);
    }
    this.contentRoot.add(object);
    this.frameContent();
  }

  frameContent() {
    const box = new THREE.Box3().setFromObject(this.contentRoot);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 0.1);
    const distance = maxDim * 2.2;
    this.controls.target.copy(center);
    this.camera.position.set(
      center.x + distance * 0.7,
      center.y + distance * 0.45,
      center.z + distance * 0.85,
    );
    this.camera.near = distance / 100;
    this.camera.far = distance * 50;
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  dispose() {
    cancelAnimationFrame(this._animationFrame);
    window.removeEventListener("resize", this._onResize);
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    this.controls.dispose();
    this.renderer.dispose();
  }
}
