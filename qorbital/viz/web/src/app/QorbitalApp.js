import * as THREE from "three";
import { loadBundle } from "../loaders/BundleLoader.js";
import { createAtomGlyphs } from "../geometry/AtomGlyphs.js";
import { createIsosurfaceMesh } from "../geometry/IsosurfaceMesh.js";
import { createDensityCloud } from "../geometry/DensityCloud.js";
import { createDensityField } from "../density/densityField.js";
import { loadGridValues } from "../density/loadGridValues.js";
import { sampleDensityPoints } from "../density/samplePoints.js";
import { SceneManager } from "../scene/SceneManager.js";
import { drawMoleculeMinimap } from "../ui/MiniMap.js";
import { disposeObject } from "../util/dispose.js";
import { initialState } from "./state.js";

export class QorbitalApp {
  /**
   * @param {Record<string, HTMLElement | HTMLInputElement | HTMLCanvasElement>} elements
   */
  constructor(elements) {
    this.elements = elements;
    this.state = { ...initialState, controlsOpen: false };
    this.sceneManager = new SceneManager(
      /** @type {HTMLCanvasElement} */ (elements.canvas),
    );
    this._contentGroup = new THREE.Group();
    this._currentBundle = null;
    this._gridValues = null;

    /** @type {HTMLInputElement} */ (elements.isovalueSlider).disabled = true;
    elements.isovalueSlider.addEventListener("input", () => {
      const value = Number(
        /** @type {HTMLInputElement} */ (elements.isovalueSlider).value,
      );
      elements.isovalueReadout.textContent = value.toFixed(3);
      elements.metaIsovalue.textContent = value.toFixed(3);
    });

    /** @type {HTMLInputElement} */ (elements.toggleCloud).checked =
      this.state.showCloud;
    /** @type {HTMLInputElement} */ (elements.toggleSurface).checked =
      this.state.showSurface;
    /** @type {HTMLInputElement} */ (elements.toggleAtoms).checked =
      this.state.showAtoms;

    elements.toggleCloud.addEventListener("change", () => {
      this.state.showCloud =
        /** @type {HTMLInputElement} */ (elements.toggleCloud).checked;
      if (this._currentBundle) {
        this.renderBundle(this._currentBundle);
      }
    });
    elements.toggleSurface.addEventListener("change", () => {
      this.state.showSurface =
        /** @type {HTMLInputElement} */ (elements.toggleSurface).checked;
      if (this._currentBundle) {
        this.renderBundle(this._currentBundle);
      }
    });
    elements.toggleAtoms.addEventListener("change", () => {
      this.state.showAtoms =
        /** @type {HTMLInputElement} */ (elements.toggleAtoms).checked;
      if (this._currentBundle) {
        this.renderBundle(this._currentBundle);
      }
    });

    window.addEventListener("keydown", (event) => {
      const key = event.key.toLowerCase();
      if (key === "h") {
        this.toggleControls();
      } else if (key === "c") {
        this._setLayerToggle("showCloud", elements.toggleCloud);
      } else if (key === "s") {
        this._setLayerToggle("showSurface", elements.toggleSurface);
      }
    });

    const params = new URLSearchParams(window.location.search);
    const bundleUrl = params.get("bundle") ?? initialState.bundleUrl;
    this.state.bundleUrl = bundleUrl;

    this.load(bundleUrl);
  }

  /**
   * @param {"showCloud" | "showSurface"} stateKey
   * @param {HTMLInputElement} input
   */
  _setLayerToggle(stateKey, input) {
    this.state[stateKey] = !this.state[stateKey];
    input.checked = this.state[stateKey];
    if (this._currentBundle) {
      this.renderBundle(this._currentBundle);
    }
  }

  toggleControls() {
    this.state.controlsOpen = !this.state.controlsOpen;
    /** @type {HTMLElement} */ (this.elements.controlsPanel).hidden =
      !this.state.controlsOpen;
  }

  /**
   * @param {string} message
   * @param {boolean} [isError]
   */
  setOverlay(message, isError = false) {
    const overlay = /** @type {HTMLElement} */ (this.elements.overlay);
    overlay.textContent = message;
    overlay.classList.toggle("hidden", !message);
    overlay.classList.toggle("error", isError);
  }

  /**
   * @param {unknown} value
   * @param {number} [digits]
   * @returns {string}
   */
  _fmtEnergy(value, digits = 5) {
    return value != null ? `${Number(value).toFixed(digits)} Ha` : "—";
  }

  /**
   * @param {Record<string, unknown>} bundle
   */
  updateHud(bundle) {
    const mol = /** @type {Record<string, unknown>} */ (bundle.molecule);
    const density = /** @type {Record<string, unknown>} */ (bundle.density);
    const refs = /** @type {Record<string, number> | undefined} */ (
      bundle.reference_energies
    );
    const backend = bundle.backend
      ? /** @type {Record<string, string>} */ (bundle.backend)
      : null;

    const label = String(mol.label ?? mol.id);
    const basis = String(mol.basis ?? "—");
    const bond = Number(mol.bond_length_angstrom ?? 0);
    const iso = Number(density.isovalue ?? density.default_isovalue ?? 0.02);
    const method = String(bundle.method ?? "unknown");
    const backendLabel = backend ? `${backend.provider}/${backend.name}` : "—";

    const modeParts = [];
    if (this.state.showCloud) modeParts.push("ρ(r) cloud");
    if (this.state.showSurface) modeParts.push("isosurface");
    const modeLabel = modeParts.length > 0 ? modeParts.join(" + ") : "layers off";

    this.elements.hudPhase.textContent = `Step 1/1 · ${method} · ${modeLabel}`;
    this.elements.metaMolecule.textContent = `${label} (${basis})`;
    this.elements.metaBond.textContent = `${bond.toFixed(2)} Å`;
    this.elements.metaBasis.textContent = basis;
    this.elements.metaMethod.textContent = method;
    this.elements.metaBackend.textContent = backendLabel;
    this.elements.metaEnergy.textContent = this._fmtEnergy(bundle.energy_hartree);
    this.elements.metaHf.textContent = refs?.hf != null ? this._fmtEnergy(refs.hf) : "—";
    this.elements.metaFci.textContent = refs?.fci != null ? this._fmtEnergy(refs.fci) : "—";
    this.elements.metaIsovalue.textContent = iso.toFixed(3);

    this.elements.moleculeLabel.textContent = label;
    /** @type {HTMLInputElement} */ (this.elements.isovalueSlider).value =
      String(iso);
    this.elements.isovalueReadout.textContent = iso.toFixed(3);

    const atoms = /** @type {Array<{symbol: string, position: number[]}>} */ (
      mol.atoms
    );
    drawMoleculeMinimap(
      /** @type {HTMLCanvasElement} */ (this.elements.minimap),
      atoms,
      { label, bondLength: bond, orbital: "1σ_g" },
    );

    const provenance = bundle.provenance
      ? /** @type {Record<string, string>} */ (bundle.provenance)
      : null;
    const runId = provenance?.run_id ?? "—";
    const densitySource =
      density.kind === "grid" && this._gridValues
        ? "DensityGrid sidecar"
        : "analytic σ-bond ρ(r)";
    this.elements.hudContext.textContent =
      `${this.state.particleCount.toLocaleString()} Monte Carlo samples from ${densitySource} ` +
      `(run ${runId}). C/S toggle cloud and isosurface.`;
  }

  /**
   * @param {Record<string, unknown>} bundle
   */
  renderBundle(bundle) {
    disposeObject(this._contentGroup);
    this._contentGroup = new THREE.Group();

    const density = /** @type {Record<string, unknown>} */ (bundle.density);

    if (this.state.showCloud) {
      const field = createDensityField(bundle, this._gridValues);
      const { positions, densities } = sampleDensityPoints(
        field,
        this.state.particleCount,
      );
      if (densities.length > 0) {
        this._contentGroup.add(createDensityCloud(positions, densities));
      }
    }

    if (this.state.showSurface && density.kind === "mesh") {
      this._contentGroup.add(createIsosurfaceMesh(density));
    }

    if (this.state.showAtoms) {
      this._contentGroup.add(
        createAtomGlyphs(/** @type {Record<string, unknown>} */ (bundle.molecule)),
      );
    }

    this.sceneManager.setContent(this._contentGroup);
    this.updateHud(bundle);
  }

  /**
   * @param {string} url
   */
  async load(url) {
    this.setOverlay("Loading…");
    try {
      const bundle = await loadBundle(url);
      this._currentBundle = bundle;
      this._gridValues = await loadGridValues(
        url,
        /** @type {Record<string, unknown>} */ (bundle.density),
      );
      this.renderBundle(bundle);
      this.setOverlay("");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.setOverlay(message, true);
      this.elements.hudContext.textContent = "Load failed.";
      console.error(err);
    }
  }

  dispose() {
    disposeObject(this._contentGroup);
    this.sceneManager.dispose();
  }
}
