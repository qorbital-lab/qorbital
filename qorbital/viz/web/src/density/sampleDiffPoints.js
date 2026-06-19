/**
 * Sample signed density differences ρ_VQE − ρ_HF at shared positions.
 */

import { sampleDensityPoints } from "./samplePoints.js";

/**
 * @typedef {import("./densityField.js").DensityField} DensityField
 */

/**
 * @param {DensityField} vqeField
 * @param {DensityField} hfField
 * @param {number} count
 * @returns {{ positions: Float32Array, densities: Float32Array }}
 */
export function sampleDiffPoints(vqeField, hfField, count) {
  const { positions, densities: _vqeDensities } = sampleDensityPoints(
    vqeField,
    count,
  );
  const n = positions.length / 3;
  const diffs = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const x = positions[i * 3];
    const y = positions[i * 3 + 1];
    const z = positions[i * 3 + 2];
    diffs[i] =
      vqeField.evaluate(x, y, z) - hfField.evaluate(x, y, z);
  }
  return { positions, densities: diffs };
}
