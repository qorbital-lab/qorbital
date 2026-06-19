import { canvasCssSize } from "./canvasSize.js";

/**
 * Compact energy ladder: HF, exact/FCI, and VQE at the same R with mHa gaps.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {{
 *   exact?: number | null,
 *   hf?: number | null,
 *   vqe?: number | null,
 * }} levels
 */
export function drawEnergyLadder(canvas, levels) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const entries = [
    {
      label: "HF",
      energy: levels.hf,
      color: "rgba(170, 170, 170, 0.95)",
      dash: [4, 3],
    },
    {
      label: "Exact",
      energy: levels.exact,
      color: "rgba(120, 200, 220, 0.95)",
      dash: [],
    },
    {
      label: "VQE",
      energy: levels.vqe,
      color: "rgba(245, 185, 110, 0.95)",
      dash: [4, 3],
    },
  ].filter((entry) => entry.energy != null && Number.isFinite(Number(entry.energy)));

  if (entries.length === 0) return;

  const sorted = [...entries].sort(
    (a, b) => Number(a.energy) - Number(b.energy),
  );
  const energies = sorted.map((entry) => Number(entry.energy));
  const eLo = energies[0];
  const eHi = energies[energies.length - 1];
  const span = Math.max(eHi - eLo, 0.0001);
  const pad = Math.max(span * 0.08, 0.0004);
  const eMin = eLo - pad;
  const eMax = eHi + pad;

  const rowCount = sorted.length;
  const { cssW } = canvasCssSize(canvas, 260, 100, 320);
  const cssH = Math.max(96, rowCount * 24 + 40);
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

  const plot = { left: 40, right: 64, top: 10, bottom: 18 };
  const plotW = cssW - plot.left - plot.right;
  const plotH = cssH - plot.top - plot.bottom;
  const baseline = cssH - plot.bottom;
  const minRowGap = 18;

  /** @param {number} energy */
  const energyToY = (energy) =>
    plot.top + ((eMax - energy) / (eMax - eMin)) * plotH;

  /** Lowest energy sits at the bottom; enforce readable row spacing. */
  const lineYs = sorted.map((entry) => energyToY(Number(entry.energy)));
  for (let i = 1; i < lineYs.length; i += 1) {
    if (lineYs[i - 1] - lineYs[i] < minRowGap) {
      lineYs[i] = lineYs[i - 1] - minRowGap;
    }
  }
  if (lineYs[lineYs.length - 1] < plot.top) {
    const shift = plot.top - lineYs[lineYs.length - 1];
    for (let i = 0; i < lineYs.length; i += 1) {
      lineYs[i] += shift;
    }
  }
  if (lineYs[0] > baseline) {
    const shift = lineYs[0] - baseline;
    for (let i = 0; i < lineYs.length; i += 1) {
      lineYs[i] -= shift;
    }
  }

  ctx.strokeStyle = "rgba(55, 55, 55, 0.35)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(plot.left, plot.top);
  ctx.lineTo(plot.left, baseline);
  ctx.stroke();

  for (let i = 0; i < sorted.length; i += 1) {
    const entry = sorted[i];
    const y = lineYs[i];

    ctx.strokeStyle = entry.color;
    ctx.lineWidth = 1.25;
    ctx.setLineDash(entry.dash);
    ctx.beginPath();
    ctx.moveTo(plot.left, y);
    ctx.lineTo(cssW - plot.right, y);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.font = '600 8px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.fillStyle = entry.color;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(entry.label, 8, y);

    ctx.font = '500 8px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.textAlign = "right";
    ctx.fillText(`${Number(entry.energy).toFixed(5)}`, cssW - 6, y);
  }

  for (let i = 0; i < sorted.length - 1; i += 1) {
    const lower = Number(sorted[i].energy);
    const upper = Number(sorted[i + 1].energy);
    const deltaMha = (upper - lower) * 1000;
    const midY = (lineYs[i] + lineYs[i + 1]) / 2;

    ctx.font = '500 7px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.fillStyle = "rgba(120, 120, 120, 0.85)";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(`${deltaMha.toFixed(1)} mHa`, plot.left + plotW / 2, midY);
  }

  ctx.font = 'italic 500 8px ui-monospace, "SF Mono", Menlo, monospace';
  ctx.fillStyle = "#555";
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText("E (Ha)  ↑ lower is better", plot.left + plotW / 2, cssH - 2);
}
