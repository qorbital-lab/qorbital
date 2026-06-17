import * as THREE from "three";
import { DENSITY_COLORMAP, sampleColormap } from "../util/colorMaps.js";
import { getDiscTexture } from "../util/sprites.js";

/**
 * Build a soft probability-cloud point sprite from sampled density points.
 *
 * Points are colored with a perceptually-uniform colormap (the scientific
 * standard), drawn as soft round sprites, and additively blended so dense
 * regions glow. Scene fog provides the depth cue that reads the spray as a
 * 3D volume rather than a flat sheet.
 *
 * @param {Float32Array} positions length 3N
 * @param {Float32Array} densities length N
 * @returns {THREE.Points}
 */
export function createDensityCloud(positions, densities) {
  const count = densities.length;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

  const colors = new Float32Array(count * 3);
  let maxRho = 0;
  for (let i = 0; i < count; i += 1) {
    maxRho = Math.max(maxRho, densities[i]);
  }
  const invPeak = maxRho > 0 ? 1 / maxRho : 1;

  for (let i = 0; i < count; i += 1) {
    const t = Math.pow(densities[i] * invPeak, 0.55);
    const [r, g, b] = sampleColormap(DENSITY_COLORMAP, t);
    colors[i * 3] = r;
    colors[i * 3 + 1] = g;
    colors[i * 3 + 2] = b;
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.07,
    map: getDiscTexture(),
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: 0.8,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    fog: true,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  return points;
}
