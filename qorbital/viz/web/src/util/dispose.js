/** Dispose Three.js GPU resources. */

/**
 * @param {import("three").Object3D | null | undefined} root
 */
export function disposeObject(root) {
  if (!root) return;
  root.traverse((child) => {
    if ("geometry" in child && child.geometry) {
      child.geometry.dispose();
    }
    if ("material" in child && child.material) {
      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material];
      for (const material of materials) {
        material.dispose();
      }
    }
  });
}
