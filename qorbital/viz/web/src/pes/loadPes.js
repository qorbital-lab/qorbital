/**
 * Load cached PES JSON from data/pes/<molecule>.json.
 */

/**
 * @typedef {{ bond_length: number, energy: number }} PesPoint
 * @typedef {{ molecule: string, points: PesPoint[] }} PesData
 */

/**
 * @param {string} url
 * @returns {Promise<PesData>}
 */
export async function loadPes(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load PES (${response.status}): ${url}`);
  }
  const data = /** @type {PesData} */ (await response.json());
  if (!Array.isArray(data.points) || data.points.length === 0) {
    throw new Error(`PES has no points: ${url}`);
  }
  return data;
}
