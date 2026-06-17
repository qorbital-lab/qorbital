/**
 * Load a trajectory ensemble manifest + its float32 sidecars.
 *
 * The manifest (`<mol>_ensemble.json`) lists one recorded VQE run per member;
 * overlaying their Bohmian trajectories forms the hardware-noise uncertainty
 * cloud. Returns `null` when a molecule has no ensemble so the caller can
 * degrade gracefully.
 *
 * @param {string} manifestUrl
 * @returns {Promise<{
 *   molecule: string,
 *   particles: number,
 *   steps: number,
 *   dt: number,
 *   members: Array<{
 *     values: Float32Array,
 *     particles: number,
 *     steps: number,
 *     dt: number,
 *     runId: string,
 *     shots: number | null,
 *     backend: string | null,
 *     energy: number | null,
 *   }>,
 * } | null>}
 */
export async function loadEnsemble(manifestUrl) {
  let manifest;
  try {
    const response = await fetch(manifestUrl);
    if (!response.ok) {
      return null;
    }
    manifest = await response.json();
  } catch {
    return null;
  }

  const runs = Array.isArray(manifest.runs) ? manifest.runs : [];
  if (runs.length === 0) {
    return null;
  }

  const base = manifestUrl.slice(0, manifestUrl.lastIndexOf("/") + 1);

  const members = await Promise.all(
    runs.map(async (run) => {
      const pathsPath = String(run.paths ?? "").trim();
      if (!pathsPath) return null;
      const sidecarUrl = pathsPath.startsWith("http")
        ? pathsPath
        : `${base}${pathsPath}`;
      const response = await fetch(sidecarUrl);
      if (!response.ok) return null;
      const values = new Float32Array(await response.arrayBuffer());
      const particles = Number(run.particles);
      const steps = Number(run.steps);
      if (values.length !== particles * steps * 3) return null;
      return {
        values,
        particles,
        steps,
        dt: Number(run.dt ?? 0.1),
        runId: String(run.run_id ?? ""),
        shots: run.shots ?? null,
        backend: run.backend ?? null,
        energy: run.energy_hartree ?? null,
      };
    }),
  );

  const loaded = members.filter((m) => m !== null);
  if (loaded.length === 0) {
    return null;
  }

  return {
    molecule: String(manifest.molecule ?? ""),
    particles: Number(manifest.particles ?? loaded[0].particles),
    steps: Number(manifest.steps ?? loaded[0].steps),
    dt: Number(manifest.dt ?? loaded[0].dt),
    members: loaded,
  };
}
