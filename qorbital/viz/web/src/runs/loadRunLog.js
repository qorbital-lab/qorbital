/**
 * Load VQE run logs from data/runs/<molecule>/<run_id>.json.
 */

/**
 * @typedef {{ iteration: number, energy: number }} OptimizerSnapshot
 * @typedef {{
 *   runId: string,
 *   history: OptimizerSnapshot[],
 *   backend: string | null,
 *   shots: number | null,
 *   electronicEnergy: number | null,
 * }} RunLogSummary
 */

/**
 * Extract optimizer snapshots from a run log, tolerating legacy key names.
 *
 * @param {Record<string, unknown>} log
 * @returns {OptimizerSnapshot[]}
 */
export function extractOptimizerHistory(log) {
  const raw =
    log?.optimizer_history ??
    log?.convergence_history ??
    [];
  if (!Array.isArray(raw)) {
    return [];
  }

  /** @type {OptimizerSnapshot[]} */
  const history = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const iteration = Number(/** @type {Record<string, unknown>} */ (entry).iteration);
    const energy = Number(/** @type {Record<string, unknown>} */ (entry).energy);
    if (!Number.isFinite(iteration) || !Number.isFinite(energy)) continue;
    history.push({ iteration, energy });
  }

  history.sort((a, b) => a.iteration - b.iteration);
  return history;
}

/**
 * @param {string} moleculeDir lowercase molecule folder (e.g. "h2", "lih")
 * @param {string} runId
 * @returns {Promise<RunLogSummary>}
 */
export async function loadRunLog(moleculeDir, runId) {
  const url = `runs/${moleculeDir}/${runId}.json`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load run log (${response.status}): ${url}`);
  }
  const log = /** @type {Record<string, unknown>} */ (await response.json());
  const history = extractOptimizerHistory(log);
  if (history.length === 0) {
    throw new Error(`Run log has no optimizer history: ${url}`);
  }

  const electronic = log.electronic_energy;
  return {
    runId: String(log.run_id ?? runId),
    history,
    backend: log.backend != null ? String(log.backend) : null,
    shots: log.shots != null ? Number(log.shots) : null,
    electronicEnergy: Number.isFinite(Number(electronic))
      ? Number(electronic)
      : null,
  };
}
