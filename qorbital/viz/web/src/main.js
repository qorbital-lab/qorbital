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
    controlsPanel: requireElement("controls-panel"),
    moleculeLabel: requireElement("molecule-label"),
    isovalueSlider: requireElement("isovalue-slider"),
    isovalueReadout: requireElement("isovalue-readout"),
    toggleCloud: requireElement("toggle-cloud"),
    toggleSurface: requireElement("toggle-surface"),
    toggleAtoms: requireElement("toggle-atoms"),
  });

  window.qorbitalApp = app;
} catch (error) {
  showBootstrapError(error);
  console.error(error);
}
