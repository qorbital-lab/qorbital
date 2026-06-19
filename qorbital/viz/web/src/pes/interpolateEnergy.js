/**
 * Linear interpolation of PES energy at an arbitrary bond length.
 */

/**
 * @param {Array<{ bond_length: number, energy: number }>} points
 * @param {number} bond
 * @returns {number}
 */
export function interpolateEnergy(points, bond) {
  if (points.length === 0) {
    return NaN;
  }

  const sorted = [...points].sort((a, b) => a.bond_length - b.bond_length);
  if (bond <= sorted[0].bond_length) {
    return sorted[0].energy;
  }
  const last = sorted[sorted.length - 1];
  if (bond >= last.bond_length) {
    return last.energy;
  }

  for (let i = 0; i < sorted.length - 1; i += 1) {
    const a = sorted[i];
    const b = sorted[i + 1];
    if (bond >= a.bond_length && bond <= b.bond_length) {
      const span = b.bond_length - a.bond_length;
      if (span <= 0) {
        return a.energy;
      }
      const t = (bond - a.bond_length) / span;
      return a.energy + t * (b.energy - a.energy);
    }
  }

  return last.energy;
}
