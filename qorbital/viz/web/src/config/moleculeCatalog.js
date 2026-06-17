/** Static molecule catalog for the web viewer. */

/**
 * @typedef {Object} MoleculeEntry
 * @property {string} id
 * @property {string} label
 * @property {string} bundleUrl
 * @property {string} pesUrl
 * @property {number} defaultBond
 * @property {number} bondMin
 * @property {number} bondMax
 */

/** @type {MoleculeEntry[]} */
export const MOLECULE_CATALOG = [
  {
    id: "H2",
    label: "H₂",
    bundleUrl: "bundles/h2/h2_bundle.json",
    pesUrl: "pes/h2.json",
    defaultBond: 0.735,
    bondMin: 0.55,
    bondMax: 1.5,
  },
  {
    id: "HeH+",
    label: "HeH⁺",
    bundleUrl: "bundles/heh+/heh+_bundle.json",
    pesUrl: "pes/heh+.json",
    defaultBond: 0.772,
    bondMin: 0.6,
    bondMax: 1.6,
  },
  {
    id: "LiH",
    label: "LiH",
    bundleUrl: "bundles/lih/lih_bundle.json",
    pesUrl: "pes/lih.json",
    defaultBond: 1.596,
    bondMin: 1.2,
    bondMax: 2.6,
  },
];

/**
 * @param {string} query
 * @returns {MoleculeEntry | undefined}
 */
export function findMoleculeById(query) {
  const normalized = query.trim().toLowerCase().replace(/\s+/g, "");
  return MOLECULE_CATALOG.find((entry) => {
    const id = entry.id.toLowerCase();
    return (
      id === normalized ||
      id.replace("+", "") === normalized.replace("+", "") ||
      entry.label.toLowerCase().replace(/[₂⁺]/g, (ch) =>
        ch === "₂" ? "2" : "+",
      ) === normalized
    );
  });
}

/**
 * @param {string} bundleUrl
 * @returns {MoleculeEntry | undefined}
 */
export function findMoleculeByBundleUrl(bundleUrl) {
  const normalized = bundleUrl.trim().toLowerCase();
  return MOLECULE_CATALOG.find((entry) =>
    normalized.endsWith(entry.bundleUrl.toLowerCase()),
  );
}

/**
 * @returns {MoleculeEntry}
 */
export function defaultMolecule() {
  return MOLECULE_CATALOG[0];
}
