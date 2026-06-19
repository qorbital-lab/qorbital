/**
 * Downsample particle-major trajectory buffers for lighter default playback.
 * Ensemble / hardware-replay paths should keep the full particle count.
 *
 * @param {Float32Array} values flat [p0_t0_xyz, p0_t1_xyz, …]
 * @param {number} particles
 * @param {number} steps
 * @param {number} maxParticles
 * @returns {{ values: Float32Array, particles: number }}
 */
export function subsampleTrajectoryValues(values, particles, steps, maxParticles) {
  if (maxParticles >= particles) {
    return { values, particles };
  }
  if (maxParticles <= 0) {
    return { values: new Float32Array(0), particles: 0 };
  }

  const stride = steps * 3;
  const out = new Float32Array(maxParticles * stride);
  for (let i = 0; i < maxParticles; i += 1) {
    const sourceParticle =
      maxParticles === 1
        ? 0
        : Math.round((i * (particles - 1)) / (maxParticles - 1));
    const srcBase = sourceParticle * stride;
    const dstBase = i * stride;
    out.set(values.subarray(srcBase, srcBase + stride), dstBase);
  }
  return { values: out, particles: maxParticles };
}
