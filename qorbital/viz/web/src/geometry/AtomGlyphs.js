import * as THREE from "three";
import { ATOM_CORE, ATOM_SHELL, BOND_COLOR } from "../util/colorMaps.js";

const ELEMENT_RADIUS = {
  H: 0.28,
  He: 0.32,
  Li: 0.45,
  Be: 0.4,
  default: 0.32,
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

  const shellGeo = new THREE.SphereGeometry(1, 16, 16);
  const shellMat = new THREE.MeshStandardMaterial({
    color: ATOM_SHELL,
    metalness: 0.0,
    roughness: 1.0,
    transparent: true,
    opacity: 0.85,
  });
  const coreGeo = new THREE.SphereGeometry(1, 12, 12);
  const coreMat = new THREE.MeshStandardMaterial({
    color: ATOM_CORE,
    emissive: new THREE.Color(0xffffff),
    emissiveIntensity: 0.25,
    metalness: 0.0,
    roughness: 0.6,
  });

  const positions = [];
  for (const atom of atoms) {
    const r = radiusFor(atom.symbol);
    const shell = new THREE.Mesh(shellGeo, shellMat);
    shell.position.set(atom.position[0], atom.position[1], atom.position[2]);
    shell.scale.setScalar(r);
    group.add(shell);

    const core = new THREE.Mesh(coreGeo, coreMat);
    core.position.copy(shell.position);
    core.scale.setScalar(r * 0.35);
    group.add(core);

    positions.push(atom.position);
  }

  if (positions.length >= 2) {
    const a = new THREE.Vector3(...positions[0]);
    const b = new THREE.Vector3(...positions[positions.length - 1]);
    const dir = new THREE.Vector3().subVectors(b, a);
    const length = dir.length();
    if (length > 1e-6) {
      const bondGeo = new THREE.CylinderGeometry(0.04, 0.04, length, 8);
      const bondMat = new THREE.MeshStandardMaterial({
        color: BOND_COLOR,
        metalness: 0.0,
        roughness: 1.0,
      });
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
