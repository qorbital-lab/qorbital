/**
 * Scale nuclear positions to a preview bond length without reloading density.
 */

/**
 * @param {Record<string, unknown>} molecule
 * @param {number} bondLength
 * @returns {Record<string, unknown>}
 */
export function scaleMoleculeBond(molecule, bondLength) {
  const id = String(molecule.id ?? "");
  const atoms = /** @type {Array<{symbol: string, position: number[]}>} */ (
    molecule.atoms
  ).map((atom) => ({
    symbol: atom.symbol,
    position: [...atom.position],
  }));

  if (id === "H2" && atoms.length === 2) {
    const half = bondLength / 2;
    atoms[0].position = [0, 0, -half];
    atoms[1].position = [0, 0, half];
  } else if ((id === "HeH+" || id === "LiH") && atoms.length === 2) {
    atoms[0].position = [0, 0, 0];
    atoms[1].position = [0, 0, bondLength];
  } else if (atoms.length >= 2) {
    const equilibrium = Number(molecule.bond_length_angstrom ?? bondLength);
    if (equilibrium > 0) {
      const scale = bondLength / equilibrium;
      const anchor = atoms[0].position;
      for (let i = 1; i < atoms.length; i += 1) {
        atoms[i].position = atoms[i].position.map(
          (coord, axis) => anchor[axis] + (atoms[i].position[axis] - anchor[axis]) * scale,
        );
      }
    }
  }

  return {
    ...molecule,
    bond_length_angstrom: bondLength,
    atoms,
  };
}
