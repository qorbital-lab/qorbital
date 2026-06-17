import * as THREE from "three";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { sampleColormap, SPEED_COLORMAP } from "../util/colorMaps.js";
import { getDiscTexture } from "../util/sprites.js";

const TRAIL_LENGTH = 16;

/**
 * Build animated Bohmian trajectory paths: a faint speed-colored fat-line
 * backdrop of the full path plus a bright "comet head" with a fading trail
 * that flows along it in time.
 *
 * The returned group carries an `update(progress01)` on `userData` that the
 * scene clock drives each frame; `progress01` cycles 0→1 over one pass.
 *
 * @param {Float32Array} values flat [p0_t0_xyz, p0_t1_xyz, …]
 * @param {number} particles
 * @param {number} steps
 * @param {number} dt time step between consecutive points
 * @param {{ opacity?: number, lineOpacity?: number }} [options]
 * @returns {THREE.Group}
 */
export function createTrajectoryPaths(values, particles, steps, dt, options = {}) {
  const group = new THREE.Group();
  const lineOpacity = options.lineOpacity ?? 0.32;
  const headOpacity = options.opacity ?? 0.95;

  const speeds = [];
  let maxSpeed = 0;
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

  /** @param {number} speed @returns {[number, number, number]} */
  const speedColor = (speed) =>
    sampleColormap(SPEED_COLORMAP, (speed * invPeak) ** 0.65);

  for (let p = 0; p < particles; p += 1) {
    const base = p * steps * 3;
    const linePositions = new Array(steps * 3);
    const lineColors = new Array(steps * 3);
    for (let t = 0; t < steps; t += 1) {
      const i = t * 3;
      linePositions[i] = values[base + i];
      linePositions[i + 1] = values[base + i + 1];
      linePositions[i + 2] = values[base + i + 2];
      const [r, g, b] = speedColor(speeds[p][t]);
      lineColors[i] = r;
      lineColors[i + 1] = g;
      lineColors[i + 2] = b;
    }

    const geometry = new LineGeometry();
    geometry.setPositions(linePositions);
    geometry.setColors(lineColors);

    const material = new LineMaterial({
      vertexColors: true,
      transparent: true,
      opacity: lineOpacity,
      linewidth: 1.6,
      depthWrite: false,
      dashed: false,
    });
    material.resolution.set(window.innerWidth || 1, window.innerHeight || 1);
    group.add(new Line2(geometry, material));
  }

  const headCount = particles * TRAIL_LENGTH;
  const headPositions = new Float32Array(headCount * 3);
  const headColors = new Float32Array(headCount * 3);
  const headGeometry = new THREE.BufferGeometry();
  headGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(headPositions, 3),
  );
  headGeometry.setAttribute("color", new THREE.BufferAttribute(headColors, 3));
  const headMaterial = new THREE.PointsMaterial({
    size: 0.16,
    map: getDiscTexture(),
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: headOpacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const heads = new THREE.Points(headGeometry, headMaterial);
  heads.frustumCulled = false;
  group.add(heads);

  /** @param {number} p @param {number} f @param {number} comp */
  const sampleAxis = (p, f, comp) => {
    const base = p * steps * 3;
    const lo = Math.floor(f);
    const hi = Math.min(lo + 1, steps - 1);
    const frac = f - lo;
    const a = values[base + lo * 3 + comp];
    const b = values[base + hi * 3 + comp];
    return a + (b - a) * frac;
  };

  const posAttr = headGeometry.getAttribute("position");
  const colAttr = headGeometry.getAttribute("color");

  /** @param {number} progress01 */
  const update = (progress01) => {
    const headF = progress01 * (steps - 1);
    let w = 0;
    for (let p = 0; p < particles; p += 1) {
      for (let k = 0; k < TRAIL_LENGTH; k += 1) {
        let f = headF - k;
        if (f < 0) f += steps - 1;
        const fade = (1 - k / TRAIL_LENGTH) ** 1.6;
        const speed = speeds[p][Math.min(Math.round(f), steps - 1)];
        const [r, g, b] = speedColor(speed);
        const i3 = w * 3;
        headPositions[i3] = sampleAxis(p, f, 0);
        headPositions[i3 + 1] = sampleAxis(p, f, 1);
        headPositions[i3 + 2] = sampleAxis(p, f, 2);
        headColors[i3] = r * fade;
        headColors[i3 + 1] = g * fade;
        headColors[i3 + 2] = b * fade;
        w += 1;
      }
    }
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
  };

  update(0);

  group.userData.update = update;
  group.userData.duration = steps * dt;
  group.userData.steps = steps;
  group.userData.dt = dt;
  group.userData.maxSpeed = maxSpeed;

  return group;
}
