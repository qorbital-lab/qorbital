import { QorbitalApp } from "./app/QorbitalApp.js";

function requireElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing required element #${id}`);
  }
  return element;
}

function showBootstrapError(error) {
  const overlay = document.getElementById("overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  overlay.classList.add("error");
  overlay.textContent =
    error instanceof Error ? error.message : String(error);
}

try {
  const app = new QorbitalApp({
    canvas: requireElement("viewer-canvas"),
    overlay: requireElement("overlay"),
    hudPhase: requireElement("hud-phase"),
    hudContext: requireElement("hud-context"),
    hudContextNote: requireElement("hud-context-note"),
    minimap: requireElement("hud-minimap"),
    metaMolecule: requireElement("meta-molecule"),
    metaBond: requireElement("meta-bond"),
    metaBasis: requireElement("meta-basis"),
    metaMethod: requireElement("meta-method"),
    metaBackend: requireElement("meta-backend"),
    metaEnergy: requireElement("meta-energy"),
    metaHf: requireElement("meta-hf"),
    metaFci: requireElement("meta-fci"),
    metaIsovalue: requireElement("meta-isovalue"),
    metaElectronCount: requireElement("meta-electron-count"),
    backendBadge: requireElement("hud-backend-badge"),
    legendDensity: requireElement("legend-density"),
    legendSpeed: requireElement("legend-speed"),
    legendDensityMax: requireElement("legend-density-max"),
    legendSpeedMax: requireElement("legend-speed-max"),
    panelIsosurface: requireElement("panel-isosurface"),
    surfaceToggleLabel: requireElement("surface-toggle-label"),
    controlsPanel: requireElement("controls-panel"),
    physicsPanel: requireElement("physics-panel"),
    physicsPesChart: requireElement("physics-pes-chart"),
    physicsEnergyLadder: requireElement("physics-energy-ladder"),
    moleculeLabel: requireElement("molecule-label"),
    moleculeSelect: requireElement("molecule-select"),
    bondSlider: requireElement("bond-slider"),
    bondReadout: requireElement("bond-readout"),
    pesChart: requireElement("pes-chart"),
    isovalueSlider: requireElement("isovalue-slider"),
    isovalueReadout: requireElement("isovalue-readout"),
    toggleCloud: requireElement("toggle-cloud"),
    toggleSurface: requireElement("toggle-surface"),
    toggleAtoms: requireElement("toggle-atoms"),
    toggleTrajectories: requireElement("toggle-trajectories"),
    toggleEnsemble: requireElement("toggle-ensemble"),
    ensembleHint: requireElement("ensemble-hint"),
    toggleComparison: requireElement("toggle-comparison"),
    toggleComparisonDiff: requireElement("toggle-comparison-diff"),
    comparisonHint: requireElement("comparison-hint"),
    trajectoryScrubber: requireElement("trajectory-scrubber"),
    convergenceInset: requireElement("convergence-inset"),
    runSelect: requireElement("run-select"),
    convergenceChart: requireElement("hud-convergence"),
  });

  window.qorbitalApp = app;
} catch (error) {
  showBootstrapError(error);
  console.error(error);
}
