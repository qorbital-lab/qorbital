/**
 * Load a float32-le density sidecar referenced by DensityGrid.values.
 */

/**
 * @param {string} bundleUrl
 * @param {Record<string, unknown>} density
 * @returns {Promise<Float32Array | null>}
 */
export async function loadGridValues(bundleUrl, density) {
  if (density.kind !== "grid") {
    return null;
  }

  const valuesPath = String(density.values ?? "").trim();
  if (!valuesPath) {
    return null;
  }

  const base = bundleUrl.slice(0, bundleUrl.lastIndexOf("/") + 1);
  const sidecarUrl = valuesPath.startsWith("http")
    ? valuesPath
    : `${base}${valuesPath}`;

  const response = await fetch(sidecarUrl);
  if (!response.ok) {
    throw new Error(`Failed to load density grid (${response.status}): ${sidecarUrl}`);
  }

  const buffer = await response.arrayBuffer();
  const values = new Float32Array(buffer);
  const shape = /** @type {number[]} */ (density.shape);
  const expected = shape[0] * shape[1] * shape[2];
  if (values.length !== expected) {
    throw new Error(
      `Density grid size mismatch: expected ${expected} values, got ${values.length}`,
    );
  }
  return values;
}
