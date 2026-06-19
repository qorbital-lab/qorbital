/**
 * Resolve responsive CSS pixel dimensions for inset chart canvases.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {number} fallbackW
 * @param {number} fallbackH
 * @param {number} [maxW] upper bound (defaults to fallbackW)
 * @returns {{ cssW: number, cssH: number }}
 */
export function canvasCssSize(canvas, fallbackW, fallbackH, maxW = fallbackW) {
  const parent = canvas.parentElement;
  const measured = parent?.clientWidth ?? 0;
  let parentW = measured > 0 ? measured : fallbackW;
  const style = getComputedStyle(canvas);
  const borderX =
    parseFloat(style.borderLeftWidth || "0") +
    parseFloat(style.borderRightWidth || "0");
  parentW = Math.max(120, parentW - borderX);
  const cssW = Math.min(maxW, Math.floor(parentW));
  return { cssW, cssH: fallbackH };
}
