import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { GRID_LINE } from "../util/colorMaps.js";

export class SceneManager {
  /**
   * @param {HTMLCanvasElement} canvas
   */
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x000000);
    // Subtle depth cue: distant fragments fade toward the black background,
    // which (with additive blending) reads the density cloud as a volume.
    this.scene.fog = new THREE.FogExp2(0x000000, 0.06);

    this.camera = new THREE.PerspectiveCamera(42, 1, 0.01, 500);
    this.camera.position.set(4, 2, 5);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      // Keep the framebuffer readable so we can export PNG frames on demand.
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.clock = new THREE.Clock();
    /** @type {Set<(elapsed: number, delta: number) => void>} */
    this._tickers = new Set();
    /** @type {Array<import("three").Material & { resolution?: THREE.Vector2 }>} */
    this._lineMaterials = [];

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, 0, 0);
    this.controls.autoRotateSpeed = 0.9;
    /** @type {(() => void) | null} */
    this._onUserInteract = null;
    this.controls.addEventListener("start", () => {
      if (this.controls.autoRotate && this._onUserInteract) {
        this._onUserInteract();
      }
    });
    /** @type {(() => void) | null} */
    this.onCameraChange = null;
    this.controls.addEventListener("end", () => {
      if (this.onCameraChange) this.onCameraChange();
    });

    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambient);
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(5, 8, 6);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xbfd4ff, 0.3);
    fill.position.set(-6, -2, -4);
    this.scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffffff, 0.55);
    rim.position.set(-3, 4, -7);
    this.scene.add(rim);

    this._addReferenceGrid();
    this._setupComposer();

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

  _setupComposer() {
    const { width, height } = this._viewSize();
    this.composer = new EffectComposer(this.renderer);
    this.composer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.composer.setSize(width, height);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloomPass = new UnrealBloomPass(
      new THREE.Vector2(width, height),
      0.65, // strength
      0.45, // radius
      0.2, // threshold — only bright (emissive / dense) regions bloom
    );
    this.composer.addPass(this.bloomPass);
    this.composer.addPass(new OutputPass());
  }

  _addReferenceGrid() {
    const grid = new THREE.GridHelper(6, 24, GRID_LINE, GRID_LINE);
    const gridMaterial = grid.material;
    if (Array.isArray(gridMaterial)) {
      for (const material of gridMaterial) {
        material.opacity = 0.25;
        material.transparent = true;
      }
    } else {
      gridMaterial.opacity = 0.25;
      gridMaterial.transparent = true;
    }
    grid.position.y = -1.2;
    this.scene.add(grid);

    const boxEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(2.8, 2.8, 2.8));
    const boxLines = new THREE.LineSegments(
      boxEdges,
      new THREE.LineBasicMaterial({
        color: GRID_LINE,
        transparent: true,
        opacity: 0.12,
      }),
    );
    this.scene.add(boxLines);

    // XYZ orientation triad parked at the grid corner.
    const axes = new THREE.AxesHelper(0.7);
    const axesMaterial = axes.material;
    if (Array.isArray(axesMaterial)) {
      for (const material of axesMaterial) {
        material.transparent = true;
        material.opacity = 0.55;
        material.fog = false;
      }
    } else {
      axesMaterial.transparent = true;
      axesMaterial.opacity = 0.55;
      axesMaterial.fog = false;
    }
    axes.position.set(-2.6, -1.19, -2.6);
    this.scene.add(axes);
  }

  resize() {
    const parent = this.canvas.parentElement;
    let width = parent?.clientWidth ?? 0;
    let height = parent?.clientHeight ?? 0;
    if (width === 0 || height === 0) {
      width = window.innerWidth;
      height = window.innerHeight;
    }
    if (width === 0 || height === 0) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
    if (this.composer) {
      this.composer.setSize(width, height);
    }
    if (this.bloomPass) {
      this.bloomPass.resolution.set(width, height);
    }
    this._syncLineResolution(width, height);
  }

  /**
   * Keep fat-line (Line2) materials aware of the viewport so their pixel
   * widths render correctly.
   *
   * @param {number} width
   * @param {number} height
   */
  _syncLineResolution(width, height) {
    for (const material of this._lineMaterials) {
      if (material.resolution) {
        material.resolution.set(width, height);
      }
    }
  }

  /**
   * Register a per-frame callback. Returns an unsubscribe function.
   *
   * @param {(elapsed: number, delta: number) => void} fn
   * @returns {() => void}
   */
  addTicker(fn) {
    this._tickers.add(fn);
    return () => this._tickers.delete(fn);
  }

  _animate() {
    const delta = this.clock.getDelta();
    const elapsed = this.clock.getElapsedTime();
    for (const ticker of this._tickers) {
      ticker(elapsed, delta);
    }
    this.controls.update();
    if (this.composer) {
      this.composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }
    this._animationFrame = requestAnimationFrame(this._animate);
  }

  /**
   * @param {THREE.Object3D} object
   */
  /**
   * Swap the rendered content. Does NOT re-frame the camera, so layer toggles
   * (trajectories, surface, ensemble, …) preserve the user's current view.
   * Call {@link frameContent} explicitly on molecule load / reset.
   *
   * @param {THREE.Object3D} object
   * @param {boolean} [frame] re-frame the camera to the new content
   */
  setContent(object, frame = false) {
    while (this.contentRoot.children.length > 0) {
      const child = this.contentRoot.children[0];
      this.contentRoot.remove(child);
    }
    this.contentRoot.add(object);
    this._collectLineMaterials();
    if (frame) {
      this.frameContent();
    }
  }

  _collectLineMaterials() {
    this._lineMaterials = [];
    this.contentRoot.traverse((child) => {
      const material = /** @type {{ isLineMaterial?: boolean }} */ (
        /** @type {unknown} */ (child).material
      );
      if (material && material.isLineMaterial) {
        this._lineMaterials.push(
          /** @type {import("three").Material & { resolution?: THREE.Vector2 }} */ (
            /** @type {unknown} */ (material)
          ),
        );
      }
    });
    const { width, height } = this._viewSize();
    this._syncLineResolution(width, height);
  }

  /**
   * @returns {{ width: number, height: number }}
   */
  _viewSize() {
    const parent = this.canvas.parentElement;
    let width = parent?.clientWidth ?? 0;
    let height = parent?.clientHeight ?? 0;
    if (width === 0 || height === 0) {
      width = window.innerWidth || 1;
      height = window.innerHeight || 1;
    }
    return { width, height };
  }

  /**
   * Fit the camera to a bounding box. Pass an explicit, layer-independent box
   * (atoms + trajectories) so the framing is stable regardless of which layers
   * are toggled on; falls back to the current content bounds when omitted.
   *
   * @param {THREE.Box3} [explicitBox]
   */
  frameContent(explicitBox) {
    const box =
      explicitBox && !explicitBox.isEmpty()
        ? explicitBox
        : new THREE.Box3().setFromObject(this.contentRoot);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 0.1);
    const distance = maxDim * 2.4;
    this.controls.target.copy(center);
    this.camera.position.set(
      center.x + distance * 0.65,
      center.y + distance * 0.4,
      center.z + distance * 0.9,
    );
    this.camera.near = distance / 100;
    this.camera.far = distance * 50;
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  /**
   * @param {boolean} enabled
   * @param {() => void} [onInteract] called once when the user grabs the camera
   */
  setAutoRotate(enabled, onInteract) {
    this.controls.autoRotate = enabled;
    this._onUserInteract = enabled ? (onInteract ?? null) : null;
  }

  /**
   * @returns {{ position: number[], target: number[] }}
   */
  getCameraState() {
    return {
      position: [
        this.camera.position.x,
        this.camera.position.y,
        this.camera.position.z,
      ],
      target: [
        this.controls.target.x,
        this.controls.target.y,
        this.controls.target.z,
      ],
    };
  }

  /**
   * @param {{ position: number[], target: number[] }} state
   */
  setCameraState(state) {
    if (!state || !state.position || !state.target) return;
    this.camera.position.set(
      state.position[0],
      state.position[1],
      state.position[2],
    );
    this.controls.target.set(state.target[0], state.target[1], state.target[2]);
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  /** Re-frame the current content (used by a "reset view" control). */
  resetView() {
    this.frameContent();
  }

  /**
   * Render one frame and return it as a PNG blob URL for download.
   *
   * @returns {Promise<Blob | null>}
   */
  captureFrame() {
    if (this.composer) {
      this.composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }
    return new Promise((resolve) => {
      this.renderer.domElement.toBlob((blob) => resolve(blob), "image/png");
    });
  }

  dispose() {
    cancelAnimationFrame(this._animationFrame);
    window.removeEventListener("resize", this._onResize);
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    this.controls.dispose();
    if (this.composer) {
      this.composer.dispose();
    }
    this.renderer.dispose();
  }
}
