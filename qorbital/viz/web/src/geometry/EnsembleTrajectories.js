import * as THREE from "three";
import { createTrajectoryPaths } from "./TrajectoryPaths.js";

/**
 * Overlay every ensemble member's Bohmian trajectories at low opacity to form
 * the hardware-noise "uncertainty cloud." Each member animates in lockstep so
 * the whole cloud shimmers together.
 *
 * @param {Array<{ values: Float32Array, particles: number, steps: number, dt: number }>} members
 * @param {{ lineOpacity?: number, opacity?: number }} [options]
 * @returns {THREE.Group}
 */
export function createEnsembleTrajectories(members, options = {}) {
  const group = new THREE.Group();
  /** @type {Array<(progress01: number) => void>} */
  const updaters = [];
  let duration = 0;
  let steps = 0;
  let dt = 0.1;
  let maxSpeed = 0;

  for (const member of members) {
    const memberGroup = createTrajectoryPaths(
      member.values,
      member.particles,
      member.steps,
      member.dt,
      {
        lineOpacity: options.lineOpacity ?? 0.09,
        opacity: options.opacity ?? 0.4,
      },
    );
    if (typeof memberGroup.userData.update === "function") {
      updaters.push(memberGroup.userData.update);
    }
    duration = Number(memberGroup.userData.duration ?? duration);
    maxSpeed = Math.max(maxSpeed, Number(memberGroup.userData.maxSpeed ?? 0));
    steps = member.steps;
    dt = member.dt;
    group.add(memberGroup);
  }

  group.userData.update = (progress01) => {
    for (const update of updaters) {
      update(progress01);
    }
  };
  group.userData.duration = duration;
  group.userData.steps = steps;
  group.userData.dt = dt;
  group.userData.maxSpeed = maxSpeed;
  group.userData.memberCount = members.length;

  return group;
}
