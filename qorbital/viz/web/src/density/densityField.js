/**
 * Evaluate electron density ρ(r) for sampling and visualization.
 */

/**
 * @typedef {Object} DensityField
 * @property {(x: number, y: number, z: number) => number} evaluate
 * @property {number} maxDensity
 * @property {{ min: number[], max: number[] }} bounds
 */

/**
 * Mock H₂ σ-bond density: two merged Gaussians along the bond axis.
 *
 * @param {number} halfBond
 * @returns {(x: number, y: number, z: number) => number}
 */
export function createH2SigmaDensity(halfBond) {
  const sigmaPerp = 0.32;
  const sigmaAx = 0.5;
  const inv2Perp = 1 / (2 * sigmaPerp * sigmaPerp);
  const inv2Ax = 1 / (2 * sigmaAx * sigmaAx);

  return (x, y, z) => {
    const r2Perp = x * x + y * y;
    const dz0 = z + halfBond;
    const dz1 = z - halfBond;
    const g0 = Math.exp(-r2Perp * inv2Perp - dz0 * dz0 * inv2Ax);
    const g1 = Math.exp(-r2Perp * inv2Perp - dz1 * dz1 * inv2Ax);
    return g0 + g1;
  };
}

/**
 * @param {number[]} origin
 * @param {number[]} spacing
 * @param {number[]} shape
 * @param {Float32Array} values
 * @returns {(x: number, y: number, z: number) => number}
 */
export function createGridDensity(origin, spacing, shape, values) {
  const [nx, ny, nz] = shape;
  const [ox, oy, oz] = origin;
  const [sx, sy, sz] = spacing;

  return (x, y, z) => {
    const fx = (x - ox) / sx;
    const fy = (y - oy) / sy;
    const fz = (z - oz) / sz;
    if (fx < 0 || fy < 0 || fz < 0 || fx > nx - 1 || fy > ny - 1 || fz > nz - 1) {
      return 0;
    }

    const ix = Math.min(Math.floor(fx), nx - 2);
    const iy = Math.min(Math.floor(fy), ny - 2);
    const iz = Math.min(Math.floor(fz), nz - 2);
    const tx = fx - ix;
    const ty = fy - iy;
    const tz = fz - iz;

    /**
     * @param {number} i
     * @param {number} j
     * @param {number} k
     * @returns {number}
     */
    const at = (i, j, k) => values[i + nx * (j + ny * k)] ?? 0;

    const c000 = at(ix, iy, iz);
    const c100 = at(ix + 1, iy, iz);
    const c010 = at(ix, iy + 1, iz);
    const c110 = at(ix + 1, iy + 1, iz);
    const c001 = at(ix, iy, iz + 1);
    const c101 = at(ix + 1, iy, iz + 1);
    const c011 = at(ix, iy + 1, iz + 1);
    const c111 = at(ix + 1, iy + 1, iz + 1);

    const c00 = c000 * (1 - tx) + c100 * tx;
    const c10 = c010 * (1 - tx) + c110 * tx;
    const c01 = c001 * (1 - tx) + c101 * tx;
    const c11 = c011 * (1 - tx) + c111 * tx;
    const c0 = c00 * (1 - ty) + c10 * ty;
    const c1 = c01 * (1 - ty) + c11 * ty;
    return c0 * (1 - tz) + c1 * tz;
  };
}

/**
 * @param {(x: number, y: number, z: number) => number} evaluate
 * @param {{ min: number[], max: number[] }} bounds
 * @param {number} [steps]
 * @returns {number}
 */
function estimateMaxDensity(evaluate, bounds, steps = 12) {
  let max = 0;
  const [minX, minY, minZ] = bounds.min;
  const [maxX, maxY, maxZ] = bounds.max;
  for (let i = 0; i <= steps; i += 1) {
    const x = minX + ((maxX - minX) * i) / steps;
    for (let j = 0; j <= steps; j += 1) {
      const y = minY + ((maxY - minY) * j) / steps;
      for (let k = 0; k <= steps; k += 1) {
        const z = minZ + ((maxZ - minZ) * k) / steps;
        max = Math.max(max, evaluate(x, y, z));
      }
    }
  }
  return max;
}

/**
 * @param {Record<string, unknown>} molecule
 * @returns {{ min: number[], max: number[] }}
 */
function boundsFromMolecule(molecule) {
  const atoms = /** @type {Array<{position: number[]}>} */ (molecule.atoms);
  const xs = atoms.map((a) => a.position[0]);
  const ys = atoms.map((a) => a.position[1]);
  const zs = atoms.map((a) => a.position[2]);
  const pad = 1.4;
  return {
    min: [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.min(...zs) - pad],
    max: [Math.max(...xs) + pad, Math.max(...ys) + pad, Math.max(...zs) + pad],
  };
}

/**
 * @param {Record<string, unknown>} bundle
 * @param {Float32Array | null} [gridValues]
 * @returns {DensityField}
 */
export function createDensityField(bundle, gridValues = null) {
  const molecule = /** @type {Record<string, unknown>} */ (bundle.molecule);
  const density = /** @type {Record<string, unknown>} */ (bundle.density);
  const bond = Number(molecule.bond_length_angstrom ?? 0.74);
  const halfBond = bond / 2;

  if (density.kind === "grid" && gridValues) {
    const origin = /** @type {number[]} */ (density.origin);
    const spacing = /** @type {number[]} */ (density.spacing);
    const shape = /** @type {number[]} */ (density.shape);
    const [nx, ny, nz] = shape;
    const [ox, oy, oz] = origin;
    const [sx, sy, sz] = spacing;
    const evaluate = createGridDensity(origin, spacing, shape, gridValues);
    const bounds = {
      min: [ox, oy, oz],
      max: [ox + sx * (nx - 1), oy + sy * (ny - 1), oz + sz * (nz - 1)],
    };
    return {
      evaluate,
      maxDensity: estimateMaxDensity(evaluate, bounds),
      bounds,
    };
  }

  const evaluate = createH2SigmaDensity(halfBond);
  const bounds = boundsFromMolecule(molecule);
  return {
    evaluate,
    maxDensity: estimateMaxDensity(evaluate, bounds),
    bounds,
  };
}
