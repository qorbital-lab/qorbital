import { QorbitalApp } from "./app/QorbitalApp.js";

const app = new QorbitalApp({
  canvas: document.getElementById("viewer-canvas"),
  overlay: document.getElementById("overlay"),
  hudPhase: document.getElementById("hud-phase"),
  hudContext: document.getElementById("hud-context"),
  minimap: document.getElementById("hud-minimap"),
  metaMolecule: document.getElementById("meta-molecule"),
  metaBond: document.getElementById("meta-bond"),
  metaBasis: document.getElementById("meta-basis"),
  metaMethod: document.getElementById("meta-method"),
  metaBackend: document.getElementById("meta-backend"),
  metaEnergy: document.getElementById("meta-energy"),
  metaHf: document.getElementById("meta-hf"),
  metaFci: document.getElementById("meta-fci"),
  metaIsovalue: document.getElementById("meta-isovalue"),
  controlsPanel: document.getElementById("controls-panel"),
  moleculeLabel: document.getElementById("molecule-label"),
  isovalueSlider: document.getElementById("isovalue-slider"),
  isovalueReadout: document.getElementById("isovalue-readout"),
});

window.qorbitalApp = app;
