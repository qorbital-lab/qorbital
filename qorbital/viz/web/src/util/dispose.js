/** Dispose Three.js GPU resources. */

/**
 * @param {import("three").Object3D | null | undefined} root
 */
export function disposeObject(root) {
  if (!root) return;
  const seenGeometries = new Set();
  const seenMaterials = new Set();
  root.traverse((child) => {
    if ("geometry" in child && child.geometry) {
      if (!seenGeometries.has(child.geometry)) {
        seenGeometries.add(child.geometry);
        child.geometry.dispose();
      }
    }
    if ("material" in child && child.material) {
      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material];
      for (const material of materials) {
        if (!seenMaterials.has(material)) {
          seenMaterials.add(material);
          material.dispose();
        }
      }
    }
  });
}
