/**
 * Draw a bond-axis ρ(r) reference inset for the HUD.
 *
 * Shows on-axis electron density vs. nuclear positions — the standard
 * 1D slice quantum chemists expect, not an ambiguous dot diagram.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{symbol: string, position: number[]}>} atoms
 * @param {{
 *   label?: string,
 *   bondLength?: number,
 *   orbital?: string,
 * }} [options]
 */
export function drawMoleculeMinimap(canvas, atoms, options = {}) {
  const ctx = canvas.getContext("2d");
  if (!ctx || atoms.length === 0) return;

  const cssW = 148;
  const cssH = 92;
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

  drawHudBrackets(ctx, cssW, cssH);

  const bondLength = resolveBondLength(atoms, options.bondLength);
  const halfBond = bondLength / 2;
  const plot = { left: 24, right: 10, top: 16, bottom: 26 };
  const plotW = cssW - plot.left - plot.right;
  const plotH = cssH - plot.top - plot.bottom;
  const zPad = 0.28;
  const zMin = -halfBond - zPad;
  const zMax = halfBond + zPad;

  /** @param {number} z */
  const zToX = (z) => plot.left + ((z - zMin) / (zMax - zMin)) * plotW;

  /** @param {number} rho @param {number} peak */
  const rhoToY = (rho, peak) =>
    plot.top + plotH - (rho / peak) * (plotH - 6);

  let peak = 0;
  const samples = 64;
  const profile = [];
  for (let i = 0; i <= samples; i += 1) {
    const z = zMin + ((zMax - zMin) * i) / samples;
    const rho = onAxisDensity(z, halfBond);
    peak = Math.max(peak, rho);
    profile.push({ z, rho });
  }
  if (peak <= 0) peak = 1;

  drawPlotFrame(ctx, plot, cssW, cssH);
  drawDensityProfile(ctx, profile, zToX, rhoToY, peak, plot, cssH);
  drawNuclearMarkers(ctx, atoms, bondLength, halfBond, zToX, plot, cssH);

  drawAxisLabel(ctx, "z", zToX(zMax) + 2, cssH - 10);
  drawAxisLabel(ctx, "ρ", 6, plot.top + 4);

  const orbital = options.orbital ?? "1σ_g";
  const molecule = options.label ?? "—";
  drawFooter(
    ctx,
    cssW,
    cssH,
    `${molecule} · ${orbital} · ${bondLength.toFixed(2)} Å`,
  );
}

/**
 * @param {Array<{position: number[]}>} atoms
 * @param {number | undefined} bondLength
 * @returns {number}
 */
function resolveBondLength(atoms, bondLength) {
  if (bondLength != null && bondLength > 0) return bondLength;
  if (atoms.length >= 2) {
    const a = atoms[0].position;
    const b = atoms[atoms.length - 1].position;
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const dz = b[2] - a[2];
    return Math.hypot(dx, dy, dz);
  }
  return 0.74;
}

/**
 * On-axis H₂ σ density at x = y = 0 (matches 3D cloud model).
 *
 * @param {number} z
 * @param {number} halfBond
 * @returns {number}
 */
function onAxisDensity(z, halfBond) {
  const sigmaAx = 0.5;
  const inv2Ax = 1 / (2 * sigmaAx * sigmaAx);
  const g0 = Math.exp(-((z + halfBond) ** 2) * inv2Ax);
  const g1 = Math.exp(-((z - halfBond) ** 2) * inv2Ax);
  return g0 + g1;
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} w
 * @param {number} h
 */
function drawHudBrackets(ctx, w, h) {
  const inset = 5;
  const len = 10;
  ctx.strokeStyle = "#383838";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(inset, inset + len);
  ctx.lineTo(inset, inset);
  ctx.lineTo(inset + len, inset);
  ctx.moveTo(w - inset - len, inset);
  ctx.lineTo(w - inset, inset);
  ctx.lineTo(w - inset, inset + len);
  ctx.moveTo(inset, h - inset - len);
  ctx.lineTo(inset, h - inset);
  ctx.lineTo(inset + len, h - inset);
  ctx.moveTo(w - inset - len, h - inset);
  ctx.lineTo(w - inset, h - inset);
  ctx.lineTo(w - inset, h - inset - len);
  ctx.stroke();
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {{ left: number, top: number, bottom: number }} plot
 * @param {number} cssW
 * @param {number} cssH
 */
function drawPlotFrame(ctx, plot, cssW, cssH) {
  const baseline = cssH - plot.bottom;
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
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<{z: number, rho: number}>} profile
 * @param {(z: number) => number} zToX
 * @param {(rho: number, peak: number) => number} rhoToY
 * @param {number} peak
 * @param {{ left: number, top: number, bottom: number }} plot
 */
function drawDensityProfile(ctx, profile, zToX, rhoToY, peak, plot, cssH) {
  const baseline = cssH - plot.bottom;

  ctx.beginPath();
  for (let i = 0; i < profile.length; i += 1) {
    const { z, rho } = profile[i];
    const x = zToX(z);
    const y = rhoToY(rho, peak);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  const last = profile[profile.length - 1];
  ctx.lineTo(zToX(last.z), baseline);
  ctx.lineTo(zToX(profile[0].z), baseline);
  ctx.closePath();

  const fill = ctx.createLinearGradient(0, plot.top, 0, baseline);
  fill.addColorStop(0, "rgba(210, 220, 230, 0.22)");
  fill.addColorStop(0.55, "rgba(160, 175, 190, 0.12)");
  fill.addColorStop(1, "rgba(80, 90, 100, 0.04)");
  ctx.fillStyle = fill;
  ctx.fill();

  ctx.strokeStyle = "rgba(210, 215, 225, 0.75)";
  ctx.lineWidth = 1.25;
  ctx.beginPath();
  for (let i = 0; i < profile.length; i += 1) {
    const { z, rho } = profile[i];
    const x = zToX(z);
    const y = rhoToY(rho, peak);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<{symbol: string, position: number[]}>} atoms
 * @param {number} bondLength
 * @param {number} halfBond
 * @param {(z: number) => number} zToX
 * @param {{ left: number, top: number, bottom: number }} plot
 * @param {number} cssH
 */
function drawNuclearMarkers(
  ctx,
  atoms,
  bondLength,
  halfBond,
  zToX,
  plot,
  cssH,
) {
  const baseline = cssH - plot.bottom;
  const zPositions =
    atoms.length === 2
      ? [-halfBond, halfBond]
      : atoms.map((a) => a.position[2]);

  for (let i = 0; i < zPositions.length; i += 1) {
    const z = zPositions[i];
    const x = zToX(z);
    const symbol = atoms[i]?.symbol ?? atoms[0]?.symbol ?? "";

    ctx.strokeStyle = "rgba(120, 120, 120, 0.55)";
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(x, plot.top + 2);
    ctx.lineTo(x, baseline + 4);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "#bdbdbd";
    ctx.beginPath();
    ctx.arc(x, baseline + 7, 2.2, 0, Math.PI * 2);
    ctx.fill();

    ctx.font = '600 8px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "#8a8a8a";
    ctx.fillText(symbol, x, baseline + 11);
  }

  if (atoms.length === 2) {
    const x0 = zToX(-halfBond);
    const x1 = zToX(halfBond);
    const y = baseline + 20;
    ctx.strokeStyle = "rgba(90, 90, 90, 0.7)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x0, y);
    ctx.lineTo(x1, y);
    ctx.moveTo(x0, y - 3);
    ctx.lineTo(x0, y + 3);
    ctx.moveTo(x1, y - 3);
    ctx.lineTo(x1, y + 3);
    ctx.stroke();

    ctx.font = '500 7px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.textAlign = "center";
    ctx.fillStyle = "#666";
    ctx.fillText(`${bondLength.toFixed(2)} Å`, (x0 + x1) / 2, y + 4);
  }
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} text
 * @param {number} x
 * @param {number} y
 */
function drawAxisLabel(ctx, text, x, y) {
  ctx.font = 'italic 500 9px ui-monospace, "SF Mono", Menlo, monospace';
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#666";
  ctx.fillText(text, x, y);
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} cssW
 * @param {number} cssH
 * @param {string} text
 */
function drawFooter(ctx, cssW, cssH, text) {
  ctx.font = '500 8px ui-monospace, "SF Mono", Menlo, monospace';
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillStyle = "#5a5a5a";
  ctx.fillText(text, cssW / 2, cssH - 7);
}
