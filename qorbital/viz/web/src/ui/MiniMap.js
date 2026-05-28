/**
 * Draw a small 2D bond-axis schematic for the HUD minimap.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{symbol: string, position: number[]}>} atoms
 */
export function drawMoleculeMinimap(canvas, atoms) {
  const ctx = canvas.getContext("2d");
  if (!ctx || atoms.length === 0) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0a0a0a";
  ctx.fillRect(0, 0, w, h);

  const xs = atoms.map((a) => a.position[0]);
  const ys = atoms.map((a) => a.position[1]);
  const zs = atoms.map((a) => a.position[2]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);

  const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 0.1);
  const pad = 12;

  /**
   * @param {number[]} pos
   * @returns {[number, number]}
   */
  const project = (pos) => {
    const nx = (pos[0] - minX) / span;
    const nz = (pos[2] - minZ) / span;
    return [pad + nx * (w - pad * 2), h - pad - nz * (h - pad * 2)];
  };

  if (atoms.length >= 2) {
    const [x0, y0] = project(atoms[0].position);
    const [x1, y1] = project(atoms[atoms.length - 1].position);
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
  }

  for (const atom of atoms) {
    const [x, y] = project(atom.position);
    ctx.fillStyle = "#888";
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#eee";
    ctx.beginPath();
    ctx.arc(x, y, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }
}
