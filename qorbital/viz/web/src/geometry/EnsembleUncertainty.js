import * as THREE from "three";
import {
  UNCERTAINTY_COLORMAP,
  sampleColormap,
} from "../util/colorMaps.js";
import { getDiscTexture } from "../util/sprites.js";

/**
 * Build a diffuse uncertainty cloud with std-tiered sprite sizes.
 *
 * @param {Float32Array} positions length 3N
 * @param {Float32Array} densities length N
 * @param {Float32Array} stds length N
 * @returns {THREE.Group}
 */
export function createEnsembleUncertainty(positions, densities, stds) {
  const count = stds.length;
  const group = new THREE.Group();

  if (count === 0) {
    return group;
  }

  const sorted = Array.from(stds).sort((a, b) => a - b);
  const p33 = sorted[Math.floor(count * 0.33)] ?? 0;
  const p66 = sorted[Math.floor(count * 0.66)] ?? p33;

  /** @type {Array<{ indices: number[], size: number, opacity: number }>} */
  const tiers = [
    { indices: [], size: 0.05, opacity: 0.75 },
    { indices: [], size: 0.09, opacity: 0.55 },
    { indices: [], size: 0.14, opacity: 0.35 },
  ];

  for (let i = 0; i < count; i += 1) {
    const s = stds[i];
    if (s <= p33) {
      tiers[0].indices.push(i);
    } else if (s <= p66) {
      tiers[1].indices.push(i);
    } else {
      tiers[2].indices.push(i);
    }
  }

  let maxRho = 0;
  for (let i = 0; i < count; i += 1) {
    maxRho = Math.max(maxRho, densities[i]);
  }
  const invPeak = maxRho > 0 ? 1 / maxRho : 1;

  for (const tier of tiers) {
    if (tier.indices.length === 0) continue;

    const n = tier.indices.length;
    const tierPositions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);

    for (let t = 0; t < n; t += 1) {
      const i = tier.indices[t];
      tierPositions[t * 3] = positions[i * 3];
      tierPositions[t * 3 + 1] = positions[i * 3 + 1];
      tierPositions[t * 3 + 2] = positions[i * 3 + 2];
      const colorT = Math.pow(densities[i] * invPeak, 0.55);
      const [r, g, b] = sampleColormap(UNCERTAINTY_COLORMAP, colorT);
      colors[t * 3] = r;
      colors[t * 3 + 1] = g;
      colors[t * 3 + 2] = b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(tierPositions, 3),
    );
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: tier.size,
      map: getDiscTexture(),
      sizeAttenuation: true,
      vertexColors: true,
      transparent: true,
      opacity: tier.opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: true,
    });

    const points = new THREE.Points(geometry, material);
    points.frustumCulled = false;
    group.add(points);
  }

  return group;
}
