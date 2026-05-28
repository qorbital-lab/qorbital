import { validateBundle } from "./validateSchema.js";

/**
 * @param {string} url
 * @returns {Promise<Record<string, unknown>>}
 */
export async function loadBundle(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load bundle (${response.status}): ${url}`);
  }
  const bundle = await response.json();
  validateBundle(bundle);
  return bundle;
}
