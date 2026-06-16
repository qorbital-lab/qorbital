/** Okabe–Ito–inspired lobe colors adapted for dark technical HUD. */

export const LOBE_POSITIVE = 0xf4f4f4;
export const LOBE_NEGATIVE = 0x4a4a4a;
export const LOBE_POSITIVE_EMISSIVE = 0x888888;
export const ATOM_CORE = 0xe8e8e8;
export const ATOM_SHELL = 0x333333;
export const BOND_COLOR = 0x444444;
export const WIREFRAME_EDGE = 0x555555;
export const GRID_LINE = 0x1a1a1a;

/**
 * @param {number} scalar
 * @returns {number} hex color
 */
export function colorFromScalar(scalar) {
  return scalar >= 0 ? LOBE_POSITIVE : LOBE_NEGATIVE;
}

/**
 * @param {number} scalar
 * @returns {number} emissive intensity factor
 */
export function emissiveFromScalar(scalar) {
  return scalar >= 0 ? 0.35 : 0.0;
}
