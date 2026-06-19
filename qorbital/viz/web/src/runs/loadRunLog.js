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
 *   mapper: string | null,
 *   twoQubitReduction: boolean | null,
 *   nuclearRepulsionEnergy: number | null,
 *   energy: number | null,
 *   timestamp: string | null,
 *   costCredits: number | null,
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
 * @param {Record<string, unknown>} log
 * @param {string} runId
 * @returns {RunLogSummary}
 */
export function parseRunLog(log, runId) {
  const history = extractOptimizerHistory(log);
  const electronic = log.electronic_energy;
  const nuclear = log.nuclear_repulsion_energy;
  const total = log.energy;
  const credits = log.cost_credits;

  return {
    runId: String(log.run_id ?? runId),
    history,
    backend: log.backend != null ? String(log.backend) : null,
    shots: log.shots != null ? Number(log.shots) : null,
    electronicEnergy: Number.isFinite(Number(electronic))
      ? Number(electronic)
      : null,
    mapper: log.mapper != null ? String(log.mapper) : null,
    twoQubitReduction:
      log.two_qubit_reduction != null
        ? Boolean(log.two_qubit_reduction)
        : null,
    nuclearRepulsionEnergy: Number.isFinite(Number(nuclear))
      ? Number(nuclear)
      : null,
    energy: Number.isFinite(Number(total)) ? Number(total) : null,
    timestamp: log.timestamp != null ? String(log.timestamp) : null,
    costCredits: Number.isFinite(Number(credits)) ? Number(credits) : null,
  };
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
  const summary = parseRunLog(log, runId);
  if (summary.history.length === 0) {
    throw new Error(`Run log has no optimizer history: ${url}`);
  }
  return summary;
}
