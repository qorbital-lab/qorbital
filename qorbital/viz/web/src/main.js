import { QorbitalApp } from "./app/QorbitalApp.js";

const canvas = /** @type {HTMLCanvasElement} */ (
  document.getElementById("viewer-canvas")
);
const overlay = /** @type {HTMLElement} */ (document.getElementById("overlay"));
const statusBar = /** @type {HTMLElement} */ (
  document.getElementById("status-bar")
);
const moleculeLabel = /** @type {HTMLElement} */ (
  document.getElementById("molecule-label")
);
const energyLabel = /** @type {HTMLElement} */ (
  document.getElementById("energy-label")
);
const isovalueSlider = /** @type {HTMLInputElement} */ (
  document.getElementById("isovalue-slider")
);
const isovalueReadout = /** @type {HTMLElement} */ (
  document.getElementById("isovalue-readout")
);

const app = new QorbitalApp({
  canvas,
  overlay,
  statusBar,
  moleculeLabel,
  energyLabel,
  isovalueSlider,
  isovalueReadout,
});

window.qorbitalApp = app;
