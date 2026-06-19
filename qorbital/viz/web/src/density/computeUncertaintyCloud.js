/**
 * Histogram Bohmian trajectory ensembles into a spatial uncertainty cloud.
 * Port of qorbital.bohmian.uncertainty.compute_uncertainty_cloud.
 */

/**
 * @typedef {{
 *   density: Float32Array,
 *   std: Float32Array,
 *   origin: number[],
 *   spacing: number[],
 *   gridShape: number[],
 * }} UncertaintyCloud
 */

/**
 * @param {number} i
 * @param {number} j
 * @param {number} k
 * @param {number} nx
 * @param {number} ny
 * @returns {number}
 */
function flatIndex(i, j, k, nx, ny) {
  return i + nx * (j + ny * k);
}

/**
 * @param {Array<{ values: Float32Array, particles: number, steps: number }>} members
 * @param {number[]} origin
 * @param {number[]} spacing
 * @param {number[]} gridShape
 * @returns {UncertaintyCloud}
 */
export function computeUncertaintyCloud(members, origin, spacing, gridShape) {
  const [nx, ny, nz] = gridShape;
  const nVoxels = nx * ny * nz;
  const counts = new Float64Array(nVoxels);
  const sumX = new Float64Array(nVoxels);
  const sumY = new Float64Array(nVoxels);
  const sumZ = new Float64Array(nVoxels);
  const sumSq = new Float64Array(nVoxels);

  const [ox, oy, oz] = origin;
  const [sx, sy, sz] = spacing;

  for (const member of members) {
    const { values, particles, steps } = member;
    const nPoints = particles * steps;
    for (let p = 0; p < nPoints; p += 1) {
      const base = p * 3;
      const x = values[base];
      const y = values[base + 1];
      const z = values[base + 2];
      const i = Math.round((x - ox) / sx);
      const j = Math.round((y - oy) / sy);
      const k = Math.round((z - oz) / sz);
      if (i < 0 || j < 0 || k < 0 || i >= nx || j >= ny || k >= nz) {
        continue;
      }
      const idx = flatIndex(i, j, k, nx, ny);
      counts[idx] += 1;
      sumX[idx] += x;
      sumY[idx] += y;
      sumZ[idx] += z;
      sumSq[idx] += x * x + y * y + z * z;
    }
  }

  let total = 0;
  for (let idx = 0; idx < nVoxels; idx += 1) {
    total += counts[idx];
  }

  const density = new Float32Array(nVoxels);
  const std = new Float32Array(nVoxels);
  const invTotal = total > 0 ? 1 / total : 0;

  for (let idx = 0; idx < nVoxels; idx += 1) {
    const c = counts[idx];
    if (c <= 0) {
      density[idx] = 0;
      std[idx] = 0;
      continue;
    }
    density[idx] = c * invTotal;
    const meanX = sumX[idx] / c;
    const meanY = sumY[idx] / c;
    const meanZ = sumZ[idx] / c;
    const meanSq = sumSq[idx] / c;
    const variance = Math.max(
      meanSq - (meanX * meanX + meanY * meanY + meanZ * meanZ),
      0,
    );
    std[idx] = Math.sqrt(variance);
  }

  return {
    density,
    std,
    origin: [...origin],
    spacing: [...spacing],
    gridShape: [...gridShape],
  };
}
