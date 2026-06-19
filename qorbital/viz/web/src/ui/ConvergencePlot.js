/**
 * Draw a compact VQE convergence curve (electronic energy vs iteration).
 */

/**
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{ iteration: number, energy: number }>} history
 * @param {{ measuredEnergy?: number | null }} [options] hardware-measured
 *   electronic energy of the converged circuit (varies per run with shot noise)
 */
export function drawConvergencePlot(canvas, history, options = {}) {
  const ctx = canvas.getContext("2d");
  if (!ctx || history.length === 0) return;

  const measuredEnergy = Number.isFinite(Number(options.measuredEnergy))
    ? Number(options.measuredEnergy)
    : null;

  const cssW = 220;
  const cssH = 88;
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

  const sorted = [...history].sort((a, b) => a.iteration - b.iteration);
  const iterMin = sorted[0].iteration;
  const iterMax = sorted[sorted.length - 1].iteration;
  let eMin = sorted[0].energy;
  let eMax = sorted[0].energy;
  for (const point of sorted) {
    eMin = Math.min(eMin, point.energy);
    eMax = Math.max(eMax, point.energy);
  }
  if (measuredEnergy != null) {
    eMin = Math.min(eMin, measuredEnergy);
    eMax = Math.max(eMax, measuredEnergy);
  }
  const ePad = Math.max((eMax - eMin) * 0.08, 0.01);
  eMin -= ePad;
  eMax += ePad;

  const plot = { left: 28, right: 10, top: 12, bottom: 22 };
  const plotW = cssW - plot.left - plot.right;
  const plotH = cssH - plot.top - plot.bottom;
  const baseline = cssH - plot.bottom;
  const iterSpan = iterMax - iterMin || 1;

  /** @param {number} iteration */
  const iterToX = (iteration) =>
    plot.left + ((iteration - iterMin) / iterSpan) * plotW;

  // Energy axis increases upward (standard convention): the most negative
  // (best) energy sits at the BOTTOM, so the optimizer curve descends to the
  // ground-state minimum and the noisier hardware value sits above it.
  /** @param {number} energy */
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

  const finalEnergy = sorted[sorted.length - 1].energy;
  const finalY = energyToY(finalEnergy);
  ctx.strokeStyle = "rgba(180, 180, 180, 0.25)";
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 3]);
  ctx.beginPath();
  ctx.moveTo(plot.left, finalY);
  ctx.lineTo(cssW - plot.right, finalY);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.beginPath();
  for (let i = 0; i < sorted.length; i += 1) {
    const { iteration, energy } = sorted[i];
    const x = iterToX(iteration);
    const y = energyToY(energy);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = "rgba(120, 200, 220, 0.85)";
  ctx.lineWidth = 1.25;
  ctx.stroke();

  // Hardware-measured energy of the converged circuit: amber line that moves
  // per run with shot noise (the optimizer curve above is the deterministic sim).
  if (measuredEnergy != null) {
    const my = energyToY(measuredEnergy);
    ctx.strokeStyle = "rgba(240, 170, 90, 0.9)";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(plot.left, my);
    ctx.lineTo(cssW - plot.right, my);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = '600 8px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.fillStyle = "rgba(245, 185, 110, 0.95)";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText(`HW ${measuredEnergy.toFixed(3)}`, cssW - plot.right, my - 2);
  }

  ctx.font = 'italic 500 9px ui-monospace, "SF Mono", Menlo, monospace';
  ctx.fillStyle = "#666";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText("iter", cssW - plot.right - 20, cssH - 8);
  ctx.save();
  ctx.translate(8, plot.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("E (Ha)", 0, 0);
  ctx.restore();
}
