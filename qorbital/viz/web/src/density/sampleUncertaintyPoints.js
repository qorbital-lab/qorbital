/**
 * Rejection-sample positions from an uncertainty histogram cloud.
 */

/**
 * @typedef {import("./computeUncertaintyCloud.js").UncertaintyCloud} UncertaintyCloud
 */

/**
 * @param {UncertaintyCloud} cloud
 * @param {number} count
 * @returns {{ positions: Float32Array, densities: Float32Array, stds: Float32Array }}
 */
export function sampleUncertaintyPoints(cloud, count) {
  const [nx, ny, nz] = cloud.gridShape;
  const [ox, oy, oz] = cloud.origin;
  const [sx, sy, sz] = cloud.spacing;
  const { density, std } = cloud;

  let maxDensity = 0;
  for (let idx = 0; idx < density.length; idx += 1) {
    maxDensity = Math.max(maxDensity, density[idx]);
  }
  const peak = maxDensity > 0 ? maxDensity : 1;

  const minX = ox;
  const minY = oy;
  const minZ = oz;
  const maxX = ox + sx * (nx - 1);
  const maxY = oy + sy * (ny - 1);
  const maxZ = oz + sz * (nz - 1);

  const positions = new Float32Array(count * 3);
  const densities = new Float32Array(count);
  const stds = new Float32Array(count);

  let accepted = 0;
  let attempts = 0;
  const maxAttempts = count * 80;

  while (accepted < count && attempts < maxAttempts) {
    attempts += 1;
    const x = minX + Math.random() * (maxX - minX);
    const y = minY + Math.random() * (maxY - minY);
    const z = minZ + Math.random() * (maxZ - minZ);

    const i = Math.min(Math.max(Math.round((x - ox) / sx), 0), nx - 1);
    const j = Math.min(Math.max(Math.round((y - oy) / sy), 0), ny - 1);
    const k = Math.min(Math.max(Math.round((z - oz) / sz), 0), nz - 1);
    const idx = i + nx * (j + ny * k);
    const rho = density[idx];
    if (rho <= 0 || Math.random() * peak > rho) {
      continue;
    }

    positions[accepted * 3] = x;
    positions[accepted * 3 + 1] = y;
    positions[accepted * 3 + 2] = z;
    densities[accepted] = rho;
    stds[accepted] = std[idx];
    accepted += 1;
  }

  if (accepted < count) {
    return {
      positions: positions.slice(0, accepted * 3),
      densities: densities.slice(0, accepted),
      stds: stds.slice(0, accepted),
    };
  }

  return { positions, densities, stds };
}
