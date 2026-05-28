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
  const molecule = /** @type {Record<string, unknown>} */ (data.molecule);
  if (!Array.isArray(molecule.atoms)) {
    throw new Error("Molecule requires atoms array");
  }
  for (const atom of molecule.atoms) {
    if (!atom || typeof atom !== "object") {
      throw new Error("Each atom must be an object");
    }
    const atomData = /** @type {Record<string, unknown>} */ (atom);
    if (!Array.isArray(atomData.position) || atomData.position.length !== 3) {
      throw new Error("Each atom.position must be a 3-element array");
    }
  }
  if (!data.density || typeof data.density !== "object") {
    throw new Error("Bundle missing density");
  }
  const density = /** @type {Record<string, unknown>} */ (data.density);
  if (!("kind" in density)) {
    throw new Error("density.kind is required");
  }
  const kind = density.kind;
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
