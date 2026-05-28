import * as THREE from "three";
import { colorFromScalar } from "../util/colorMaps.js";

/**
 * Build an isosurface mesh from ADR-004 MeshSurface data.
 *
 * @param {Record<string, unknown>} density
 * @returns {THREE.Mesh}
 */
export function createIsosurfaceMesh(density) {
  const vertices = /** @type {number[][]} */ (density.vertices);
  const faces = /** @type {number[][]} */ (density.faces);
  const scalars = /** @type {number[] | undefined} */ (density.vertex_scalars);

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(vertices.length * 3);
  for (let i = 0; i < vertices.length; i += 1) {
    positions[i * 3] = vertices[i][0];
    positions[i * 3 + 1] = vertices[i][1];
    positions[i * 3 + 2] = vertices[i][2];
  }
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

  const index = [];
  for (const face of faces) {
    index.push(face[0], face[1], face[2]);
  }
  geometry.setIndex(index);
  geometry.computeVertexNormals();

  let material;
  if (scalars && scalars.length === vertices.length) {
    const colors = new Float32Array(vertices.length * 3);
    const color = new THREE.Color();
    for (let i = 0; i < vertices.length; i += 1) {
      color.setHex(colorFromScalar(scalars[i]));
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      metalness: 0.1,
      roughness: 0.65,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.88,
    });
  } else {
    material = new THREE.MeshStandardMaterial({
      color: 0x4477aa,
      metalness: 0.1,
      roughness: 0.65,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.88,
    });
  }

  return new THREE.Mesh(geometry, material);
}
