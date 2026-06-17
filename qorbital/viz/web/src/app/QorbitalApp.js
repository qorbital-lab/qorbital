import * as THREE from "three";
import { loadBundle } from "../loaders/BundleLoader.js";
import { createAtomGlyphs } from "../geometry/AtomGlyphs.js";
import { createIsosurfaceMesh } from "../geometry/IsosurfaceMesh.js";
import { createDensityCloud } from "../geometry/DensityCloud.js";
import { createTrajectoryPaths } from "../geometry/TrajectoryPaths.js";
import { createEnsembleTrajectories } from "../geometry/EnsembleTrajectories.js";
import { scaleMoleculeBond } from "../geometry/scaleMoleculeBond.js";
import { createDensityField } from "../density/densityField.js";
import { loadGridValues } from "../density/loadGridValues.js";
import { sampleDensityPoints } from "../density/samplePoints.js";
import { loadTrajectoryValues } from "../trajectories/loadTrajectoryValues.js";
import { loadEnsemble } from "../trajectories/loadEnsemble.js";
import {
  defaultMolecule,
  findMoleculeByBundleUrl,
  findMoleculeById,
  MOLECULE_CATALOG,
} from "../config/moleculeCatalog.js";
import { loadPes } from "../pes/loadPes.js";
import { interpolateEnergy } from "../pes/interpolateEnergy.js";
import { SceneManager } from "../scene/SceneManager.js";
import { drawMoleculeMinimap } from "../ui/MiniMap.js";
import { drawPesChart } from "../ui/PesChart.js";
import { drawColorbar } from "../ui/Legend.js";
import { DENSITY_COLORMAP, SPEED_COLORMAP } from "../util/colorMaps.js";
import { disposeObject } from "../util/dispose.js";
import { initialState } from "./state.js";

/** Wall-clock seconds for one full pass of the Bohmian trajectory animation. */
const TRAJECTORY_PERIOD_SECONDS = 7;

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
    this._trajectoryValues = null;
    /** @type {Array<THREE.Group>} */
    this._animatedGroups = [];
    this._trajDuration = 0;
    this._ensembleCount = 0;
    /** @type {Awaited<ReturnType<typeof loadEnsemble>>} */
    this._ensemble = null;
    this._trajTime = 0;
    this._trajProgress = 0;
    this._hudPhaseBase = "";
    this._densityPeak = 0;
    this._speedPeak = 0;
    this._currentHasMesh = false;
    this._tourActive = false;
    this._deepLinkApplied = false;
    /** @type {Record<string, HTMLElement | null>} */
    this._toolbar = {};

    drawColorbar(
      /** @type {HTMLCanvasElement} */ (this.elements.legendDensity),
      DENSITY_COLORMAP,
    );
    drawColorbar(
      /** @type {HTMLCanvasElement} */ (this.elements.legendSpeed),
      SPEED_COLORMAP,
    );
    /** @type {import("../config/moleculeCatalog.js").MoleculeEntry | null} */
    this._currentMolecule = null;
    /** @type {Array<{ bond_length: number, energy: number }> | null} */
    this._pesPoints = null;

    this._deepLink = this._parseDeepLink();

    this._populateMoleculeSelect();
    this._wireLayerToggles();
    this._wireMoleculeControls();
    this._wireKeyboardShortcuts();
    this._wireToolbar();

    this.sceneManager.addTicker((elapsed, delta) => this._onTick(elapsed, delta));
    this.sceneManager.onCameraChange = () => this._writeUrl();
    this._onLayoutResize = () => this._syncToolbarClearance();
    window.addEventListener("resize", this._onLayoutResize);

    const entry = this._resolveInitialMolecule();
    this.selectMolecule(entry).then(() => {
      this._syncToolbarClearance();
    });
  }

  /** Keep footer HUD above the bottom toolbar as it wraps. */
  _syncToolbarClearance() {
    const toolbar = document.getElementById("hud-toolbar");
    if (!toolbar) return;
    const rect = toolbar.getBoundingClientRect();
    const clearance = Math.ceil(rect.height) + 20;
    document.documentElement.style.setProperty(
      "--toolbar-offset",
      `${clearance}px`,
    );
  }

  /**
   * Parse shareable deep-link params (layers, bond, play, camera) and apply
   * the layer/play parts to initial state. Returns the bond/camera overrides
   * for the first molecule load.
   *
   * @returns {{ bond?: number, camera?: { position: number[], target: number[] } }}
   */
  _parseDeepLink() {
    const params = new URLSearchParams(window.location.search);
    /** @type {{ bond?: number, camera?: { position: number[], target: number[] } }} */
    const link = {};

    const layers = params.get("layers");
    if (layers != null) {
      this.state.showCloud = layers.includes("c");
      this.state.showSurface = layers.includes("s");
      this.state.showAtoms = layers.includes("a");
      this.state.showTrajectories = layers.includes("t");
      this.state.showEnsemble = layers.includes("e");
    }
    if (params.get("play") === "0") {
      this.state.trajectoryPlaying = false;
    }
    const bond = Number(params.get("bond"));
    if (Number.isFinite(bond) && bond > 0) {
      link.bond = bond;
    }
    const cam = params.get("cam");
    if (cam) {
      const n = cam.split(",").map(Number);
      if (n.length === 6 && n.every((v) => Number.isFinite(v))) {
        link.camera = { position: n.slice(0, 3), target: n.slice(3, 6) };
      }
    }
    return link;
  }

  /**
   * Per-frame driver for the Bohmian trajectory animation.
   *
   * @param {number} _elapsed
   * @param {number} delta
   */
  _onTick(_elapsed, delta) {
    if (this._animatedGroups.length === 0) {
      return;
    }
    if (this.state.trajectoryPlaying) {
      this._trajTime += delta;
    }
    const cycles = this._trajTime / TRAJECTORY_PERIOD_SECONDS;
    this._trajProgress = ((cycles % 1) + 1) % 1;
    for (const group of this._animatedGroups) {
      group.userData.update(this._trajProgress);
    }
    this._renderPhase();
  }

  _renderPhase() {
    if (this._animatedGroups.length > 0) {
      const tNow = this._trajProgress * this._trajDuration;
      const playState = this.state.trajectoryPlaying ? "playing" : "paused";
      this.elements.hudPhase.textContent =
        `t ${tNow.toFixed(1)}/${this._trajDuration.toFixed(1)} a.u. · ${playState} · ${this._hudPhaseBase}`;
    } else {
      this.elements.hudPhase.textContent = this._hudPhaseBase;
    }
  }

  _populateMoleculeSelect() {
    const select = /** @type {HTMLSelectElement} */ (
      this.elements.moleculeSelect
    );
    select.replaceChildren();
    for (const entry of MOLECULE_CATALOG) {
      const option = document.createElement("option");
      option.value = entry.id;
      option.textContent = entry.label;
      select.appendChild(option);
    }
  }

  _wireLayerToggles() {
    /** @type {HTMLInputElement} */ (this.elements.isovalueSlider).disabled = true;
    this.elements.isovalueSlider.addEventListener("input", () => {
      const value = Number(
        /** @type {HTMLInputElement} */ (this.elements.isovalueSlider).value,
      );
      this.elements.isovalueReadout.textContent = value.toFixed(3);
      this.elements.metaIsovalue.textContent = value.toFixed(3);
    });

    /** @type {Array<[HTMLElement, "showCloud" | "showSurface" | "showAtoms" | "showTrajectories" | "showEnsemble"]>} */
    const bindings = [
      [this.elements.toggleCloud, "showCloud"],
      [this.elements.toggleSurface, "showSurface"],
      [this.elements.toggleAtoms, "showAtoms"],
      [this.elements.toggleTrajectories, "showTrajectories"],
      [this.elements.toggleEnsemble, "showEnsemble"],
    ];
    for (const [el, key] of bindings) {
      el.addEventListener("change", () => {
        this._setLayerState(
          key,
          /** @type {HTMLInputElement} */ (el).checked,
        );
      });
    }
    this._syncLayerUi();
  }

  /**
   * Single funnel for all layer-visibility changes (checkbox, keyboard,
   * toolbar, preset). Keeps state, every UI surface, and the URL in sync.
   *
   * @param {"showCloud" | "showSurface" | "showAtoms" | "showTrajectories" | "showEnsemble"} key
   * @param {boolean} value
   */
  _setLayerState(key, value) {
    if (key === "showEnsemble" && !this._ensemble) value = false;
    if (key === "showSurface" && !this._currentHasMesh) value = false;
    this.state[key] = value;
    this._syncLayerUi();
    if (this._currentBundle) {
      this.renderBundle(this._currentBundle);
    }
    this._writeUrl();
  }

  /**
   * @param {boolean} value
   */
  _setPlaying(value) {
    this.state.trajectoryPlaying = value;
    this._syncLayerUi();
    this._renderPhase();
    this._writeUrl();
  }

  /** Reflect current state across checkboxes and toolbar buttons. */
  _syncLayerUi() {
    /** @param {HTMLElement | undefined} input @param {boolean} on */
    const check = (input, on) => {
      if (input) /** @type {HTMLInputElement} */ (input).checked = on;
    };
    check(this.elements.toggleCloud, this.state.showCloud);
    check(this.elements.toggleSurface, this.state.showSurface);
    check(this.elements.toggleAtoms, this.state.showAtoms);
    check(this.elements.toggleTrajectories, this.state.showTrajectories);
    check(this.elements.toggleEnsemble, this.state.showEnsemble);

    /** @param {HTMLElement | null | undefined} el @param {boolean} on */
    const active = (el, on) => {
      if (el) el.dataset.active = on ? "true" : "false";
    };
    active(this._toolbar.cloud, this.state.showCloud);
    active(this._toolbar.surface, this.state.showSurface);
    active(this._toolbar.traj, this.state.showTrajectories);
    active(this._toolbar.ensemble, this.state.showEnsemble);
    active(this._toolbar.tour, this._tourActive);
    if (this._toolbar.play) {
      this._toolbar.play.dataset.active = this.state.trajectoryPlaying
        ? "true"
        : "false";
      this._toolbar.play.textContent = this.state.trajectoryPlaying
        ? "Pause"
        : "Play";
    }
  }

  /**
   * Enable/disable the ensemble controls based on whether the current
   * molecule has a loaded ensemble, and reflect it in the hint text.
   */
  _refreshEnsembleAvailability() {
    const toggle = /** @type {HTMLInputElement} */ (this.elements.toggleEnsemble);
    const available = Boolean(this._ensemble);
    toggle.disabled = !available;
    if (this._toolbar.ensemble) {
      /** @type {HTMLButtonElement} */ (this._toolbar.ensemble).disabled =
        !available;
    }
    if (!available) {
      this.state.showEnsemble = false;
      this.elements.ensembleHint.textContent = "No ensemble for this molecule";
    } else {
      const count = this._ensemble.members.length;
      this.elements.ensembleHint.textContent = `Overlay of ${count} IonQ VQE runs — noise cloud`;
    }
    this._syncLayerUi();
  }

  _wireToolbar() {
    const byId = (id) => document.getElementById(id);
    this._toolbar = {
      cloud: byId("btn-cloud"),
      surface: byId("btn-surface"),
      traj: byId("btn-traj"),
      ensemble: byId("btn-ensemble"),
      play: byId("btn-play"),
      tour: byId("btn-tour"),
    };
    /** @param {string} id @param {() => void} fn */
    const onClick = (id, fn) => {
      const el = byId(id);
      if (el) {
        el.addEventListener("click", (event) => {
          fn();
          /** @type {HTMLElement} */ (event.currentTarget).blur();
        });
      }
    };
    onClick("btn-cloud", () =>
      this._setLayerState("showCloud", !this.state.showCloud),
    );
    onClick("btn-surface", () =>
      this._setLayerState("showSurface", !this.state.showSurface),
    );
    onClick("btn-traj", () =>
      this._setLayerState("showTrajectories", !this.state.showTrajectories),
    );
    onClick("btn-ensemble", () =>
      this._setLayerState("showEnsemble", !this.state.showEnsemble),
    );
    onClick("btn-play", () => this._setPlaying(!this.state.trajectoryPlaying));
    onClick("btn-preset-copenhagen", () => this._applyPreset("copenhagen"));
    onClick("btn-preset-bohmian", () => this._applyPreset("bohmian"));
    onClick("btn-preset-ensemble", () => this._applyPreset("ensemble"));
    onClick("btn-tour", () => this._setTour(!this._tourActive));
    onClick("btn-reset", () => {
      this._setTour(false);
      this.sceneManager.resetView();
    });
    onClick("btn-save", () => this._saveFrame());
    this._syncLayerUi();
  }

  /**
   * Apply a curated view preset.
   *
   * @param {"copenhagen" | "bohmian" | "ensemble"} name
   */
  _applyPreset(name) {
    /** @type {Record<string, Partial<typeof this.state>>} */
    const presets = {
      copenhagen: {
        showCloud: true,
        showSurface: this._currentHasMesh,
        showTrajectories: false,
        showEnsemble: false,
        showAtoms: true,
      },
      bohmian: {
        showCloud: false,
        showSurface: false,
        showTrajectories: true,
        showEnsemble: false,
        showAtoms: true,
      },
      ensemble: {
        showCloud: true,
        showSurface: false,
        showTrajectories: true,
        showEnsemble: Boolean(this._ensemble),
        showAtoms: true,
      },
    };
    const preset = presets[name];
    if (!preset) return;
    Object.assign(this.state, preset);
    if (!this._ensemble) this.state.showEnsemble = false;
    if (!this._currentHasMesh) this.state.showSurface = false;
    this._syncLayerUi();
    if (this._currentBundle) {
      this.renderBundle(this._currentBundle);
    }
    this._writeUrl();
  }

  /**
   * @param {boolean} enabled
   */
  _setTour(enabled) {
    this._tourActive = enabled;
    this.sceneManager.setAutoRotate(enabled, () => this._setTour(false));
    this._syncLayerUi();
  }

  async _saveFrame() {
    const blob = await this.sceneManager.captureFrame();
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const mol = this._currentMolecule?.id?.toLowerCase() ?? "qorbital";
    anchor.href = url;
    anchor.download = `qorbital_${mol}_${Date.now()}.png`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  /** Write the shareable deep-link into the URL (replaceState, no churn). */
  _writeUrl() {
    if (!this._currentMolecule) return;
    const params = new URLSearchParams(window.location.search);
    params.set("molecule", this._currentMolecule.id.toLowerCase());
    params.delete("bundle");
    let layers = "";
    if (this.state.showCloud) layers += "c";
    if (this.state.showSurface) layers += "s";
    if (this.state.showAtoms) layers += "a";
    if (this.state.showTrajectories) layers += "t";
    if (this.state.showEnsemble) layers += "e";
    params.set("layers", layers || "0");
    const bond = this.state.previewBond ?? this._currentMolecule.defaultBond;
    params.set("bond", bond.toFixed(2));
    params.set("play", this.state.trajectoryPlaying ? "1" : "0");
    const cam = this.sceneManager.getCameraState();
    params.set(
      "cam",
      [...cam.position, ...cam.target].map((v) => v.toFixed(2)).join(","),
    );
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
  }

  _wireMoleculeControls() {
    this.elements.moleculeSelect.addEventListener("change", () => {
      const id = /** @type {HTMLSelectElement} */ (
        this.elements.moleculeSelect
      ).value;
      const entry = findMoleculeById(id);
      if (entry) {
        this.selectMolecule(entry);
      }
    });

    this.elements.bondSlider.addEventListener("input", () => {
      const bond = Number(
        /** @type {HTMLInputElement} */ (this.elements.bondSlider).value,
      );
      this.onBondChange(bond);
    });
  }

  _wireKeyboardShortcuts() {
    window.addEventListener("keydown", (event) => {
      const key = event.key.toLowerCase();
      if (key === "h") {
        this.toggleControls();
      } else if (key === "c") {
        this._setLayerState("showCloud", !this.state.showCloud);
      } else if (key === "s") {
        this._setLayerState("showSurface", !this.state.showSurface);
      } else if (key === "t") {
        this._setLayerState("showTrajectories", !this.state.showTrajectories);
      } else if (key === "e") {
        this._setLayerState("showEnsemble", !this.state.showEnsemble);
      } else if (key === " ") {
        event.preventDefault();
        this._setPlaying(!this.state.trajectoryPlaying);
      }
    });
  }

  /**
   * @returns {import("../config/moleculeCatalog.js").MoleculeEntry}
   */
  _resolveInitialMolecule() {
    const params = new URLSearchParams(window.location.search);
    const moleculeParam = params.get("molecule");
    if (moleculeParam) {
      const entry = findMoleculeById(moleculeParam);
      if (entry) {
        return entry;
      }
    }

    const bundleParam = params.get("bundle");
    if (bundleParam) {
      const entry = findMoleculeByBundleUrl(bundleParam);
      if (entry) {
        return entry;
      }
    }

    return defaultMolecule();
  }

  /**
   * @param {import("../config/moleculeCatalog.js").MoleculeEntry} entry
   */
  async selectMolecule(entry) {
    this._currentMolecule = entry;
    this.state.bundleUrl = entry.bundleUrl;

    const firstLoad = !this._deepLinkApplied;
    const linkBond = this._deepLink.bond;
    const initialBond =
      firstLoad && linkBond && linkBond >= entry.bondMin && linkBond <= entry.bondMax
        ? linkBond
        : entry.defaultBond;
    this.state.previewBond = initialBond;

    /** @type {HTMLSelectElement} */ (this.elements.moleculeSelect).value =
      entry.id;

    const slider = /** @type {HTMLInputElement} */ (this.elements.bondSlider);
    slider.min = String(entry.bondMin);
    slider.max = String(entry.bondMax);
    slider.step = "0.01";
    slider.value = String(initialBond);
    this.elements.bondReadout.textContent = `${initialBond.toFixed(2)} Å`;

    try {
      this._pesPoints = (await loadPes(entry.pesUrl)).points;
      drawPesChart(
        /** @type {HTMLCanvasElement} */ (this.elements.pesChart),
        this._pesPoints,
        initialBond,
      );
    } catch (err) {
      console.warn("PES load failed:", err);
      this._pesPoints = null;
    }

    this._ensemble = entry.ensembleUrl
      ? await loadEnsemble(entry.ensembleUrl)
      : null;
    this._refreshEnsembleAvailability();

    await this.load(entry.bundleUrl);
    this.onBondChange(initialBond);

    if (firstLoad) {
      if (this._deepLink.camera) {
        this.sceneManager.setCameraState(this._deepLink.camera);
      }
      this._deepLinkApplied = true;
    }
    this._writeUrl();
  }

  /**
   * @param {number} bond
   */
  onBondChange(bond) {
    this.state.previewBond = bond;
    this.elements.bondReadout.textContent = `${bond.toFixed(2)} Å`;
    this.elements.metaBond.textContent = `${bond.toFixed(2)} Å`;

    if (this._pesPoints) {
      const energy = interpolateEnergy(this._pesPoints, bond);
      this.elements.metaEnergy.textContent = this._fmtEnergy(energy);
      drawPesChart(
        /** @type {HTMLCanvasElement} */ (this.elements.pesChart),
        this._pesPoints,
        bond,
      );
    }

    if (this._currentBundle) {
      this.renderBundle(this._currentBundle);
    }
    if (this._deepLinkApplied) {
      this._writeUrl();
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
    const equilibriumBond = Number(mol.bond_length_angstrom ?? 0);
    const previewBond = this.state.previewBond ?? equilibriumBond;
    const iso = Number(density.isovalue ?? density.default_isovalue ?? 0.02);
    const method = String(bundle.method ?? "unknown");
    const backendLabel = backend ? `${backend.provider}/${backend.name}` : "—";

    const modeParts = [];
    if (this.state.showCloud) modeParts.push("ρ(r) cloud");
    if (this.state.showSurface) modeParts.push("isosurface");
    if (this.state.showTrajectories && this._trajectoryValues) {
      modeParts.push("trajectories");
    }
    if (this.state.showEnsemble && this._ensembleCount > 0) {
      modeParts.push(`ensemble ×${this._ensembleCount}`);
    }
    const modeLabel = modeParts.length > 0 ? modeParts.join(" + ") : "layers off";

    this._hudPhaseBase = `${method} · ${modeLabel}`;
    this._renderPhase();
    this.elements.metaMolecule.textContent = `${label} (${basis})`;
    this.elements.metaBond.textContent = `${previewBond.toFixed(2)} Å`;
    this.elements.metaBasis.textContent = basis;
    this.elements.metaMethod.textContent = method;
    this.elements.metaBackend.textContent = backendLabel;

    if (!this._pesPoints) {
      this.elements.metaEnergy.textContent = this._fmtEnergy(bundle.energy_hartree);
    }

    this.elements.metaHf.textContent = refs?.hf != null ? this._fmtEnergy(refs.hf) : "—";
    this.elements.metaFci.textContent = refs?.fci != null ? this._fmtEnergy(refs.fci) : "—";
    this.elements.metaIsovalue.textContent = iso.toFixed(3);

    this.elements.moleculeLabel.textContent = label;
    /** @type {HTMLInputElement} */ (this.elements.isovalueSlider).value =
      String(iso);
    this.elements.isovalueReadout.textContent = iso.toFixed(3);

    const displayMolecule = scaleMoleculeBond(mol, previewBond);
    const atoms = /** @type {Array<{symbol: string, position: number[]}>} */ (
      displayMolecule.atoms
    );
    drawMoleculeMinimap(
      /** @type {HTMLCanvasElement} */ (this.elements.minimap),
      atoms,
      { label, bondLength: previewBond, orbital: "1σ_g" },
    );

    const provenance = bundle.provenance
      ? /** @type {Record<string, string>} */ (bundle.provenance)
      : null;
    const runId = provenance?.run_id ?? "—";

    const bondDrift = Math.abs(previewBond - equilibriumBond) > 0.01;
    const pesNote = bondDrift
      ? ` ρ(r) from equilibrium VQE bundle at R₀=${equilibriumBond.toFixed(2)} Å; energy interpolated from PES.`
      : "";

    this.elements.hudContext.textContent =
      `${this.state.particleCount.toLocaleString()} ρ samples · run ${runId}` +
      (this.state.showEnsemble && this._ensembleCount > 0
        ? ` · ${this._ensembleCount} IonQ runs overlaid`
        : "") +
      pesNote;

    this._updateBackendBadge(backend);
    this._updateLegend();
    this._refreshSurfaceAvailability(density);
  }

  /**
   * Promote the quantum backend to a first-class badge, favoring the IonQ
   * ensemble provenance when active.
   *
   * @param {Record<string, string> | null} backend
   */
  _updateBackendBadge(backend) {
    const badge = this.elements.backendBadge;
    if (this.state.showEnsemble && this._ensemble?.members?.length) {
      const member = this._ensemble.members[0];
      const name = String(member.backend ?? "ionq").replace(/_/g, " ");
      const shots = member.shots != null ? ` · ${member.shots} shots` : "";
      badge.textContent = `IonQ · ${name}${shots} · ×${this._ensemble.members.length} runs`;
    } else if (backend) {
      badge.textContent = `${backend.provider} / ${backend.name}`;
    } else {
      badge.textContent = "—";
    }
  }

  _updateLegend() {
    this.elements.legendDensityMax.textContent =
      this._densityPeak > 0 ? this._densityPeak.toFixed(3) : "—";
    this.elements.legendSpeedMax.textContent =
      this._speedPeak > 0 ? this._speedPeak.toFixed(2) : "—";
  }

  /**
   * The isosurface layer + isovalue slider only apply to mesh bundles. Gate
   * both rather than leaving visibly dead controls.
   *
   * @param {Record<string, unknown>} density
   */
  _refreshSurfaceAvailability(density) {
    const hasMesh = density.kind === "mesh";
    this._currentHasMesh = hasMesh;
    const toggle = /** @type {HTMLInputElement} */ (this.elements.toggleSurface);
    toggle.disabled = !hasMesh;
    if (this._toolbar.surface) {
      /** @type {HTMLButtonElement} */ (this._toolbar.surface).disabled = !hasMesh;
    }
    this.elements.surfaceToggleLabel.classList.toggle("disabled", !hasMesh);
    /** @type {HTMLElement} */ (this.elements.panelIsosurface).hidden = !hasMesh;
    if (!hasMesh && this.state.showSurface) {
      this.state.showSurface = false;
      toggle.checked = false;
    }
    this._syncLayerUi();
  }

  /**
   * @param {Record<string, unknown>} bundle
   */
  renderBundle(bundle) {
    disposeObject(this._contentGroup);
    this._contentGroup = new THREE.Group();
    this._animatedGroups = [];
    this._ensembleCount = 0;

    const density = /** @type {Record<string, unknown>} */ (bundle.density);
    const mol = /** @type {Record<string, unknown>} */ (bundle.molecule);
    const equilibriumBond = Number(mol.bond_length_angstrom ?? 0);
    const previewBond = this.state.previewBond ?? equilibriumBond;
    const displayMolecule = scaleMoleculeBond(mol, previewBond);

    this._densityPeak = 0;
    this._speedPeak = 0;

    if (this.state.showCloud) {
      const field = createDensityField(bundle, this._gridValues);
      this._densityPeak = field.maxDensity;
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
      this._contentGroup.add(createAtomGlyphs(displayMolecule));
    }

    if (this.state.showTrajectories && this._trajectoryValues && bundle.trajectories) {
      const trajectories = /** @type {Record<string, unknown>} */ (
        bundle.trajectories
      );
      const particles = Number(trajectories.particles);
      const steps = Number(trajectories.steps);
      const dt = Number(trajectories.dt ?? 0.1);
      const paths = createTrajectoryPaths(
        this._trajectoryValues,
        particles,
        steps,
        dt,
      );
      this._animatedGroups.push(paths);
      this._trajDuration = Number(paths.userData.duration ?? steps * dt);
      this._speedPeak = Math.max(
        this._speedPeak,
        Number(paths.userData.maxSpeed ?? 0),
      );
      this._contentGroup.add(paths);
    }

    if (this.state.showEnsemble && this._ensemble) {
      const ensemble = createEnsembleTrajectories(this._ensemble.members);
      this._animatedGroups.push(ensemble);
      this._ensembleCount = this._ensemble.members.length;
      this._trajDuration = Number(ensemble.userData.duration ?? this._trajDuration);
      this._speedPeak = Math.max(
        this._speedPeak,
        Number(ensemble.userData.maxSpeed ?? 0),
      );
      this._contentGroup.add(ensemble);
    }

    this.sceneManager.setContent(this._contentGroup);
    this.updateHud(bundle);
    this._syncToolbarClearance();
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
      this._trajectoryValues = await loadTrajectoryValues(
        url,
        /** @type {Record<string, unknown> | undefined} */ (bundle.trajectories),
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
    window.removeEventListener("resize", this._onLayoutResize);
    disposeObject(this._contentGroup);
    this.sceneManager.dispose();
  }
}
