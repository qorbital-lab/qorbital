import * as THREE from "three";

/**
 * Build speed-colored Bohmian trajectory lines from a particle-major sidecar.
 *
 * @param {Float32Array} values flat [p0_t0_xyz, p0_t1_xyz, …]
 * @param {number} particles
 * @param {number} steps
 * @param {number} dt time step between consecutive points
 * @returns {THREE.Group}
 */
export function createTrajectoryPaths(values, particles, steps, dt) {
  const group = new THREE.Group();
  let maxSpeed = 0;

  const speeds = [];
  for (let p = 0; p < particles; p += 1) {
    const particleSpeeds = new Float32Array(steps);
    const base = p * steps * 3;
    for (let t = 0; t < steps - 1; t += 1) {
      const i0 = base + t * 3;
      const i1 = base + (t + 1) * 3;
      const dx = values[i1] - values[i0];
      const dy = values[i1 + 1] - values[i0 + 1];
      const dz = values[i1 + 2] - values[i0 + 2];
      const speed = Math.hypot(dx, dy, dz) / dt;
      particleSpeeds[t] = speed;
      maxSpeed = Math.max(maxSpeed, speed);
    }
    particleSpeeds[steps - 1] = particleSpeeds[steps - 2] ?? 0;
    speeds.push(particleSpeeds);
  }

  const invPeak = maxSpeed > 0 ? 1 / maxSpeed : 1;
  const color = new THREE.Color();

  for (let p = 0; p < particles; p += 1) {
    const positions = new Float32Array(steps * 3);
    const colors = new Float32Array(steps * 3);
    const base = p * steps * 3;

    for (let t = 0; t < steps; t += 1) {
      const i = t * 3;
      positions[i] = values[base + i];
      positions[i + 1] = values[base + i + 1];
      positions[i + 2] = values[base + i + 2];

      const tNorm = (speeds[p][t] * invPeak) ** 0.65;
      color.setRGB(0.0 + tNorm * 0.35, 0.75 + tNorm * 0.25, 0.85 + tNorm * 0.15);
      colors[i] = color.r;
      colors[i + 1] = color.g;
      colors[i + 2] = color.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const material = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.88,
      depthWrite: false,
    });
    group.add(new THREE.Line(geometry, material));
  }

  return group;
}
