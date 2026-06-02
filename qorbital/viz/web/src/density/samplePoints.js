/**
 * Monte Carlo rejection sampling from a density field ρ(r).
 */

/**
 * @typedef {import("./densityField.js").DensityField} DensityField
 */

/**
 * @param {DensityField} field
 * @param {number} count
 * @returns {{ positions: Float32Array, densities: Float32Array }}
 */
export function sampleDensityPoints(field, count) {
  const { evaluate, maxDensity, bounds } = field;
  const positions = new Float32Array(count * 3);
  const densities = new Float32Array(count);
  const [minX, minY, minZ] = bounds.min;
  const [maxX, maxY, maxZ] = bounds.max;
  const peak = maxDensity > 0 ? maxDensity : 1;

  let accepted = 0;
  let attempts = 0;
  const maxAttempts = count * 80;

  while (accepted < count && attempts < maxAttempts) {
    attempts += 1;
    const x = minX + Math.random() * (maxX - minX);
    const y = minY + Math.random() * (maxY - minY);
    const z = minZ + Math.random() * (maxZ - minZ);
    const rho = evaluate(x, y, z);
    if (rho <= 0 || Math.random() * peak > rho) {
      continue;
    }
    positions[accepted * 3] = x;
    positions[accepted * 3 + 1] = y;
    positions[accepted * 3 + 2] = z;
    densities[accepted] = rho;
    accepted += 1;
  }

  if (accepted < count) {
    return {
      positions: positions.slice(0, accepted * 3),
      densities: densities.slice(0, accepted),
    };
  }

  return { positions, densities };
}
