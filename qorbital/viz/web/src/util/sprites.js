import * as THREE from "three";

/** @type {THREE.Texture | null} */
let discTexture = null;

/**
 * Soft radial-gradient disc texture for point sprites. Built once and shared
 * so re-renders don't leak GPU textures. Turns square GL points into round,
 * volumetric-looking haze.
 *
 * @returns {THREE.Texture}
 */
export function getDiscTexture() {
  if (discTexture) {
    return discTexture;
  }
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const half = size / 2;
    const gradient = ctx.createRadialGradient(half, half, 0, half, half, half);
    gradient.addColorStop(0.0, "rgba(255, 255, 255, 1.0)");
    gradient.addColorStop(0.35, "rgba(255, 255, 255, 0.65)");
    gradient.addColorStop(0.7, "rgba(255, 255, 255, 0.18)");
    gradient.addColorStop(1.0, "rgba(255, 255, 255, 0.0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
  }
  discTexture = new THREE.CanvasTexture(canvas);
  discTexture.colorSpace = THREE.SRGBColorSpace;
  return discTexture;
}
