import { canvasCssSize } from "./canvasSize.js";

/**
 * Draw exact PES with a bond-length marker (energy increases upward).
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{ bond_length: number, energy: number }>} points
 * @param {number} currentBond
 * @param {{ equilibriumBond?: number }} [refs]
 */
export function drawEnergyPesChart(canvas, points, currentBond, refs = {}) {
  const ctx = canvas.getContext("2d");
  if (!ctx || points.length === 0) return;

  const { cssW } = canvasCssSize(canvas, 260, 132, 320);
  const cssH = Math.max(124, Math.round(cssW * 0.48));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const bg = ctx.createLinearGradient(0, 0, 0, cssH);
  bg.addColorStop(0, "#0e0e0e");
  bg.addColorStop(1, "#050505");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, cssW, cssH);

  const sorted = [...points].sort((a, b) => a.bond_length - b.bond_length);
  const bondMin = sorted[0].bond_length;
  const bondMax = sorted[sorted.length - 1].bond_length;
  let eMin = sorted[0].energy;
  let eMax = sorted[0].energy;
  for (const point of sorted) {
    eMin = Math.min(eMin, point.energy);
    eMax = Math.max(eMax, point.energy);
  }
  const ePad = Math.max((eMax - eMin) * 0.08, 0.01);
  eMin -= ePad;
  eMax += ePad;

  const plot = { left: 34, right: 12, top: 18, bottom: 26 };
  const plotW = cssW - plot.left - plot.right;
  const plotH = cssH - plot.top - plot.bottom;
  const baseline = cssH - plot.bottom;

  /** @param {number} bond */
  const bondToX = (bond) =>
    plot.left + ((bond - bondMin) / (bondMax - bondMin)) * plotW;

  /** @param {number} energy — lower (more negative) energy maps to the bottom */
  const energyToY = (energy) =>
    plot.top + ((eMax - energy) / (eMax - eMin)) * plotH;

  ctx.strokeStyle = "rgba(70, 70, 70, 0.45)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(plot.left, baseline);
  ctx.lineTo(cssW - plot.right, baseline);
  ctx.stroke();

  ctx.strokeStyle = "rgba(55, 55, 55, 0.35)";
  ctx.setLineDash([2, 3]);
  ctx.beginPath();
  ctx.moveTo(plot.left, plot.top);
  ctx.lineTo(plot.left, baseline);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.beginPath();
  for (let i = 0; i < sorted.length; i += 1) {
    const { bond_length: bond, energy } = sorted[i];
    const x = bondToX(bond);
    const y = energyToY(energy);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = "rgba(120, 200, 220, 0.85)";
  ctx.lineWidth = 1.25;
  ctx.stroke();

  const markerX = bondToX(
    Math.min(Math.max(currentBond, bondMin), bondMax),
  );
  ctx.strokeStyle = "rgba(240, 240, 240, 0.9)";
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(markerX, plot.top);
  ctx.lineTo(markerX, baseline);
  ctx.stroke();
  ctx.setLineDash([]);

  if (refs.equilibriumBond != null && Number.isFinite(refs.equilibriumBond)) {
    const r0X = bondToX(
      Math.min(Math.max(refs.equilibriumBond, bondMin), bondMax),
    );
    ctx.strokeStyle = "rgba(100, 100, 100, 0.35)";
    ctx.lineWidth = 1;
    ctx.setLineDash([1, 3]);
    ctx.beginPath();
    ctx.moveTo(r0X, plot.top);
    ctx.lineTo(r0X, baseline);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.font = 'italic 500 9px ui-monospace, "SF Mono", Menlo, monospace';
  ctx.fillStyle = "#666";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText("R (Å)", cssW - plot.right - 24, cssH - 8);
  ctx.save();
  ctx.translate(10, plot.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("E (Ha)", 0, 0);
  ctx.restore();
}
