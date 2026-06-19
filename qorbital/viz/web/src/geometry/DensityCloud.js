import * as THREE from "three";
import {
  DENSITY_COLORMAP,
  sampleColormap,
} from "../util/colorMaps.js";
import { getDiscTexture } from "../util/sprites.js";

/**
 * Build a soft probability-cloud point sprite from sampled density points.
 *
 * @param {Float32Array} positions length 3N
 * @param {Float32Array} densities length N
 * @param {{
 *   colormap?: string,
 *   opacity?: number,
 *   gamma?: number,
 *   signed?: boolean,
 * }} [options]
 * @returns {THREE.Points}
 */
export function createDensityCloud(positions, densities, options = {}) {
  const {
    colormap = DENSITY_COLORMAP,
    opacity = 0.8,
    gamma = 0.55,
    signed = false,
  } = options;

  const count = densities.length;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

  const colors = new Float32Array(count * 3);
  let scale = 0;

  if (signed) {
    for (let i = 0; i < count; i += 1) {
      scale = Math.max(scale, Math.abs(densities[i]));
    }
    const invScale = scale > 0 ? 1 / scale : 1;
    for (let i = 0; i < count; i += 1) {
      const t = (densities[i] * invScale + 1) * 0.5;
      const [r, g, b] = sampleColormap(colormap, t);
      colors[i * 3] = r;
      colors[i * 3 + 1] = g;
      colors[i * 3 + 2] = b;
    }
  } else {
    for (let i = 0; i < count; i += 1) {
      scale = Math.max(scale, densities[i]);
    }
    const invPeak = scale > 0 ? 1 / scale : 1;
    for (let i = 0; i < count; i += 1) {
      const t = Math.pow(densities[i] * invPeak, gamma);
      const [r, g, b] = sampleColormap(colormap, t);
      colors[i * 3] = r;
      colors[i * 3 + 1] = g;
      colors[i * 3 + 2] = b;
    }
  }

  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.07,
    map: getDiscTexture(),
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    fog: true,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  return points;
}
