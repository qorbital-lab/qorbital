/** Okabe–Ito–inspired lobe colors adapted for dark technical HUD. */

export const LOBE_POSITIVE = 0xf4f4f4;
export const LOBE_NEGATIVE = 0x4a4a4a;
export const LOBE_POSITIVE_EMISSIVE = 0x888888;
export const ATOM_CORE = 0xe8e8e8;
export const ATOM_SHELL = 0x333333;
export const BOND_COLOR = 0x444444;
export const WIREFRAME_EDGE = 0x555555;
export const GRID_LINE = 0x1a1a1a;

/**
 * @param {number} scalar
 * @returns {number} hex color
 */
export function colorFromScalar(scalar) {
  return scalar >= 0 ? LOBE_POSITIVE : LOBE_NEGATIVE;
}

/**
 * @param {number} scalar
 * @returns {number} emissive intensity factor
 */
export function emissiveFromScalar(scalar) {
  return scalar >= 0 ? 0.35 : 0.0;
}

/**
 * Perceptually-uniform colormap anchor stops (sRGB, 0–1). Sampled and
 * interpolated by {@link sampleColormap}. These are the scientific standard:
 * monotonic in lightness and colorblind-safe.
 *
 * @type {Record<string, number[][]>}
 */
const COLORMAPS = {
  viridis: [
    [0.267, 0.005, 0.329],
    [0.283, 0.141, 0.458],
    [0.254, 0.265, 0.53],
    [0.207, 0.372, 0.553],
    [0.164, 0.471, 0.558],
    [0.128, 0.567, 0.551],
    [0.135, 0.659, 0.518],
    [0.267, 0.749, 0.441],
    [0.478, 0.821, 0.318],
    [0.741, 0.873, 0.15],
    [0.993, 0.906, 0.144],
  ],
  inferno: [
    [0.001, 0.0, 0.014],
    [0.087, 0.044, 0.224],
    [0.258, 0.039, 0.406],
    [0.417, 0.09, 0.433],
    [0.578, 0.148, 0.404],
    [0.735, 0.215, 0.33],
    [0.865, 0.317, 0.226],
    [0.954, 0.469, 0.099],
    [0.987, 0.646, 0.039],
    [0.964, 0.843, 0.273],
    [0.988, 0.998, 0.645],
  ],
  diff: [
    [0.122, 0.467, 0.706],
    [0.259, 0.572, 0.776],
    [0.596, 0.757, 0.851],
    [0.843, 0.843, 0.843],
    [0.992, 0.749, 0.435],
    [0.843, 0.404, 0.031],
    [0.647, 0.0, 0.149],
  ],
  plasma: [
    [0.05, 0.03, 0.063],
    [0.253, 0.026, 0.446],
    [0.417, 0.0, 0.658],
    [0.636, 0.078, 0.706],
    [0.853, 0.267, 0.615],
    [0.988, 0.553, 0.388],
    [0.94, 0.975, 0.131],
  ],
};

/**
 * Sample a perceptually-uniform colormap at normalized position t∈[0,1].
 *
 * @param {keyof typeof COLORMAPS | string} name
 * @param {number} t
 * @returns {[number, number, number]} sRGB triple in 0–1
 */
export function sampleColormap(name, t) {
  const stops = COLORMAPS[name] ?? COLORMAPS.viridis;
  const clamped = t <= 0 ? 0 : t >= 1 ? 1 : t;
  const scaled = clamped * (stops.length - 1);
  const i = Math.min(Math.floor(scaled), stops.length - 2);
  const f = scaled - i;
  const a = stops[i];
  const b = stops[i + 1];
  return [
    a[0] + (b[0] - a[0]) * f,
    a[1] + (b[1] - a[1]) * f,
    a[2] + (b[2] - a[2]) * f,
  ];
}

/**
 * CSS rgb() string for a colormap sample — handy for 2D canvas legends.
 *
 * @param {string} name
 * @param {number} t
 * @returns {string}
 */
export function colormapCss(name, t) {
  const [r, g, b] = sampleColormap(name, t);
  return `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`;
}

/** Field → colormap assignment, shared across geometry + legends. */
export const DENSITY_COLORMAP = "viridis";
export const HF_COLORMAP = "inferno";
export const DIFF_COLORMAP = "diff";
export const UNCERTAINTY_COLORMAP = "plasma";
export const SPEED_COLORMAP = "inferno";
