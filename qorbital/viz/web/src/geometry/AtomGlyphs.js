import * as THREE from "three";
import { ATOM_HYDROGEN, BOND_COLOR } from "../util/colorMaps.js";

const ELEMENT_RADIUS = {
  H: 0.35,
  He: 0.4,
  Li: 0.55,
  Be: 0.5,
  default: 0.4,
};

/**
 * @param {string} symbol
 * @returns {number}
 */
function radiusFor(symbol) {
  return ELEMENT_RADIUS[symbol] ?? ELEMENT_RADIUS.default;
}

/**
 * @param {Record<string, unknown>} molecule
 * @returns {THREE.Group}
 */
export function createAtomGlyphs(molecule) {
  const group = new THREE.Group();
  const atoms = /** @type {Array<{symbol: string, position: number[]}>} */ (
    molecule.atoms
  );

  const sphereGeo = new THREE.SphereGeometry(1, 20, 20);
  const atomMaterial = new THREE.MeshStandardMaterial({
    color: ATOM_HYDROGEN,
    metalness: 0.2,
    roughness: 0.5,
  });

  const positions = [];
  for (const atom of atoms) {
    const r = radiusFor(atom.symbol);
    const mesh = new THREE.Mesh(sphereGeo, atomMaterial);
    mesh.position.set(atom.position[0], atom.position[1], atom.position[2]);
    mesh.scale.setScalar(r);
    group.add(mesh);
    positions.push(atom.position);
  }

  if (positions.length >= 2) {
    const a = new THREE.Vector3(...positions[0]);
    const b = new THREE.Vector3(...positions[positions.length - 1]);
    const dir = new THREE.Vector3().subVectors(b, a);
    const length = dir.length();
    if (length > 1e-6) {
      const bondGeo = new THREE.CylinderGeometry(0.06, 0.06, length, 12);
      const bondMat = new THREE.MeshStandardMaterial({ color: BOND_COLOR });
      const bond = new THREE.Mesh(bondGeo, bondMat);
      bond.position.copy(a).add(b).multiplyScalar(0.5);
      bond.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        dir.normalize(),
      );
      group.add(bond);
    }
  }

  return group;
}
