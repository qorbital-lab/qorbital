import * as THREE from "three";
import { colorFromScalar, emissiveFromScalar, WIREFRAME_EDGE } from "../util/colorMaps.js";
import { extractIsosurface } from "./marchingCubes.js";

/**
 * Build an isosurface mesh from ADR-004 MeshSurface data.
 *
 * @param {Record<string, unknown>} density
 * @returns {THREE.Group}
 */
export function createIsosurfaceMesh(density) {
  const vertices = /** @type {number[][]} */ (density.vertices);
  const faces = /** @type {number[][]} */ (density.faces);
  const scalars = /** @type {number[] | undefined} */ (density.vertex_scalars);

  const group = new THREE.Group();
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
      metalness: 0.05,
      roughness: 0.85,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.92,
      emissive: new THREE.Color(0x666666),
      emissiveIntensity: 0.25,
    });
  } else {
    material = new THREE.MeshStandardMaterial({
      color: 0x444444,
      metalness: 0.05,
      roughness: 0.85,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.9,
    });
  }

  const mesh = new THREE.Mesh(geometry, material);
  group.add(mesh);

  const edges = new THREE.EdgesGeometry(geometry, 12);
  const wireframe = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({
      color: WIREFRAME_EDGE,
      transparent: true,
      opacity: 0.35,
    }),
  );
  group.add(wireframe);

  if (scalars && scalars.length === vertices.length) {
    for (let i = 0; i < vertices.length; i += 1) {
      if (scalars[i] >= 0 && emissiveFromScalar(scalars[i]) > 0) {
        material.emissive = new THREE.Color(0xffffff);
        material.emissiveIntensity = 0.08;
        break;
      }
    }
  }

  return group;
}

/**
 * Extract and render an isosurface from a density grid sidecar.
 *
 * @param {Float32Array} values
 * @param {Record<string, unknown>} density
 * @param {number} isovalue
 * @returns {THREE.Group | null}
 */
export function createGridIsosurface(values, density, isovalue) {
  const origin = /** @type {number[]} */ (density.origin);
  const spacing = /** @type {number[]} */ (density.spacing);
  const shape = /** @type {number[]} */ (density.shape);

  const { positions, indices, triangleCount } = extractIsosurface(
    values,
    origin,
    spacing,
    shape,
    isovalue,
  );
  if (triangleCount === 0) {
    return null;
  }

  const group = new THREE.Group();
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeVertexNormals();

  const material = new THREE.MeshStandardMaterial({
    color: 0x6aa8ff,
    metalness: 0.08,
    roughness: 0.72,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.22,
    depthWrite: false,
    emissive: new THREE.Color(0x2a4a8a),
    emissiveIntensity: 0.35,
    blending: THREE.AdditiveBlending,
  });

  const mesh = new THREE.Mesh(geometry, material);
  group.add(mesh);

  const edges = new THREE.EdgesGeometry(geometry, 18);
  const wireframe = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({
      color: WIREFRAME_EDGE,
      transparent: true,
      opacity: 0.12,
      depthWrite: false,
    }),
  );
  group.add(wireframe);

  return group;
}
