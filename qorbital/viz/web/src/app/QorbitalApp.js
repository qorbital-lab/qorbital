import * as THREE from "three";
import { loadBundle } from "../loaders/BundleLoader.js";
import { createAtomGlyphs } from "../geometry/AtomGlyphs.js";
import { createIsosurfaceMesh } from "../geometry/IsosurfaceMesh.js";
import { SceneManager } from "../scene/SceneManager.js";
import { disposeObject } from "../util/dispose.js";
import { initialState } from "./state.js";

export class QorbitalApp {
  /**
   * @param {{
   *   canvas: HTMLCanvasElement,
   *   overlay: HTMLElement,
   *   statusBar: HTMLElement,
   *   moleculeLabel: HTMLElement,
   *   energyLabel: HTMLElement,
   *   isovalueSlider: HTMLInputElement,
   *   isovalueReadout: HTMLElement,
   * }} elements
   */
  constructor(elements) {
    this.elements = elements;
    this.state = { ...initialState };
    this.sceneManager = new SceneManager(elements.canvas);
    this._contentGroup = new THREE.Group();
    this._surfaceMesh = null;
    this._atomGroup = null;

    elements.isovalueSlider.disabled = true;
    elements.isovalueSlider.addEventListener("input", () => {
      const value = Number(elements.isovalueSlider.value);
      elements.isovalueReadout.textContent = value.toFixed(3);
    });

    this.load(this.state.bundleUrl);
  }

  /**
   * @param {string} message
   * @param {boolean} [isError]
   */
  setOverlay(message, isError = false) {
    const { overlay } = this.elements;
    overlay.textContent = message;
    overlay.classList.toggle("hidden", !message);
    overlay.classList.toggle("error", isError);
  }

  /**
   * @param {Record<string, unknown>} bundle
   */
  updateSidebar(bundle) {
    const mol = /** @type {Record<string, unknown>} */ (bundle.molecule);
    this.elements.moleculeLabel.textContent = String(mol.label ?? mol.id);
    const energy =
      bundle.energy_hartree != null
        ? `${Number(bundle.energy_hartree).toFixed(5)} Ha`
        : "—";
    this.elements.energyLabel.textContent = energy;
    const density = /** @type {Record<string, unknown>} */ (bundle.density);
    const iso = Number(density.isovalue ?? 0.02);
    this.elements.isovalueSlider.value = String(iso);
    this.elements.isovalueReadout.textContent = iso.toFixed(3);
  }

  /**
   * @param {Record<string, unknown>} bundle
   */
  renderBundle(bundle) {
    disposeObject(this._contentGroup);
    this._contentGroup = new THREE.Group();
    this._surfaceMesh = null;
    this._atomGroup = null;

    const density = /** @type {Record<string, unknown>} */ (bundle.density);
    if (density.kind === "grid") {
      throw new Error(
        "DensityGrid marching cubes not implemented yet (see issue #24)",
      );
    }

    if (this.state.showSurface) {
      this._surfaceMesh = createIsosurfaceMesh(density);
      this._contentGroup.add(this._surfaceMesh);
    }

    if (this.state.showAtoms) {
      this._atomGroup = createAtomGlyphs(
        /** @type {Record<string, unknown>} */ (bundle.molecule),
      );
      this._contentGroup.add(this._atomGroup);
    }

    this.sceneManager.setContent(this._contentGroup);
    this.updateSidebar(bundle);

    const method = String(bundle.method ?? "unknown");
    const backend = bundle.backend
      ? /** @type {Record<string, string>} */ (bundle.backend)
      : null;
    const backendLabel = backend
      ? `${backend.provider}/${backend.name}`
      : "—";
    this.elements.statusBar.textContent = `Method: ${method} · Backend: ${backendLabel} · Drag to orbit · Scroll to zoom`;
  }

  /**
   * @param {string} url
   */
  async load(url) {
    this.setOverlay("Loading…");
    try {
      const bundle = await loadBundle(url);
      this.renderBundle(bundle);
      this.setOverlay("");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.setOverlay(message, true);
      this.elements.statusBar.textContent = "Load failed";
      console.error(err);
    }
  }

  dispose() {
    disposeObject(this._contentGroup);
    this.sceneManager.dispose();
  }
}
