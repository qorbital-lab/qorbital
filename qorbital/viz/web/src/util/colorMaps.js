/** Okabe–Ito–inspired lobe colors (ADR-004 visual parity spec). */

export const LOBE_POSITIVE = 0x4477aa;
export const LOBE_NEGATIVE = 0xee7733;
export const ATOM_HYDROGEN = 0xffffff;
export const BOND_COLOR = 0x666680;

/**
 * @param {number} scalar
 * @returns {number} hex color
 */
export function colorFromScalar(scalar) {
  return scalar >= 0 ? LOBE_POSITIVE : LOBE_NEGATIVE;
}
