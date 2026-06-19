/**
 * Load a float32-le trajectory sidecar referenced by TrajectorySet.paths.
 */

/**
 * @param {string} bundleUrl
 * @param {Record<string, unknown> | null | undefined} trajectories
 * @returns {Promise<Float32Array | null>}
 */
export async function loadTrajectoryValues(bundleUrl, trajectories) {
  if (!trajectories || typeof trajectories !== "object") {
    return null;
  }

  const pathsPath = String(trajectories.paths ?? "").trim();
  if (!pathsPath) {
    return null;
  }

  const base = bundleUrl.slice(0, bundleUrl.lastIndexOf("/") + 1);
  const sidecarUrl = pathsPath.startsWith("http")
    ? pathsPath
    : `${base}${pathsPath}`;

  const response = await fetch(sidecarUrl);
  if (!response.ok) {
    throw new Error(
      `Failed to load trajectory sidecar (${response.status}): ${sidecarUrl}`,
    );
  }

  const buffer = await response.arrayBuffer();
  const values = new Float32Array(buffer);
  const particles = Number(trajectories.particles);
  const steps = Number(trajectories.steps);
  const expected = particles * steps * 3;
  if (values.length !== expected) {
    throw new Error(
      `Trajectory size mismatch: expected ${expected} values, got ${values.length}`,
    );
  }
  return values;
}
