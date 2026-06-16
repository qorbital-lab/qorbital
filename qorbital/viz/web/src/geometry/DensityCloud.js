import * as THREE from "three";

/**
 * Build a soft probability-cloud point sprite from sampled density points.
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
  const color = new THREE.Color();

  for (let i = 0; i < count; i += 1) {
    const t = Math.pow(densities[i] * invPeak, 0.55);
    color.setRGB(0.55 + t * 0.4, 0.58 + t * 0.35, 0.62 + t * 0.3);
    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.045,
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: 0.72,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  return new THREE.Points(geometry, material);
}
