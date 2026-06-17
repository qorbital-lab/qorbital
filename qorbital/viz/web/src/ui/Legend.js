import { colormapCss } from "../util/colorMaps.js";

/**
 * Paint a horizontal colorbar (low → high, left → right) for a field legend.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {string} colormapName
 */
export function drawColorbar(canvas, colormapName) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const cssW = 84;
  const cssH = 8;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const stops = 48;
  for (let i = 0; i < stops; i += 1) {
    const t = i / (stops - 1);
    ctx.fillStyle = colormapCss(colormapName, t);
    ctx.fillRect((i / stops) * cssW, 0, cssW / stops + 1, cssH);
  }

  ctx.strokeStyle = "rgba(120, 120, 120, 0.4)";
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, cssW - 1, cssH - 1);
}
