/** Minimal ADR-004 validation for browser bundles. */

const SUPPORTED_MAJOR = 0;

/**
 * @param {unknown} bundle
 * @returns {asserts bundle is Record<string, unknown>}
 */
export function validateBundle(bundle) {
  if (!bundle || typeof bundle !== "object") {
    throw new Error("Bundle must be a JSON object");
  }
  const data = /** @type {Record<string, unknown>} */ (bundle);
  const version = String(data.schema_version ?? "");
  const major = parseInt(version.split(".")[0], 10);
  if (Number.isNaN(major) || major !== SUPPORTED_MAJOR) {
    throw new Error(`Unsupported schema_version: ${version || "(missing)"}`);
  }
  if (!data.molecule || typeof data.molecule !== "object") {
    throw new Error("Bundle missing molecule");
  }
  if (!data.density || typeof data.density !== "object") {
    throw new Error("Bundle missing density");
  }
  const density = /** @type {Record<string, unknown>} */ (data.density);
  const kind = density.kind ?? "mesh";
  if (kind === "mesh") {
    if (!Array.isArray(density.vertices) || !Array.isArray(density.faces)) {
      throw new Error("MeshSurface requires vertices and faces arrays");
    }
  } else if (kind === "grid") {
    if (!Array.isArray(density.shape)) {
      throw new Error("DensityGrid requires shape");
    }
  } else {
    throw new Error(`Unknown density kind: ${kind}`);
  }
}
