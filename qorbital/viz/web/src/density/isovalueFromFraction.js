/**
 * Physically motivated isosurface level from an electron-density grid.
 *
 * Chooses the density threshold that encloses a target fraction of the
 * integrated probability (electron count).
 */

/**
 * @param {Float32Array} values
 * @param {number[]} spacing
 * @returns {{ electronCount: number, dV: number }}
 */
export function integratedElectronCount(values, spacing) {
  const dV = spacing[0] * spacing[1] * spacing[2];
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
  }
  return { electronCount: sum * dV, dV };
}

/**
 * @param {Float32Array} values
 * @param {number[]} spacing
 * @param {number} fraction Target enclosed fraction in (0, 1].
 * @returns {{ isovalue: number, electronCount: number, enclosedFraction: number, actualFraction: number }}
 */
export function isovalueFromFraction(values, spacing, fraction) {
  const { electronCount, dV } = integratedElectronCount(values, spacing);
  const target = electronCount * Math.min(1, Math.max(0, fraction));

  if (target <= 0 || values.length === 0) {
    return {
      isovalue: 0,
      electronCount,
      enclosedFraction: fraction,
      actualFraction: 0,
    };
  }

  const weighted = [];
  for (let i = 0; i < values.length; i += 1) {
    const rho = values[i];
    if (rho > 0) {
      weighted.push({ rho, mass: rho * dV });
    }
  }
  weighted.sort((a, b) => b.rho - a.rho);

  let accumulated = 0;
  let isovalue = weighted.length > 0 ? weighted[weighted.length - 1].rho : 0;
  for (const entry of weighted) {
    accumulated += entry.mass;
    isovalue = entry.rho;
    if (accumulated >= target) {
      break;
    }
  }

  const actualFraction = electronCount > 0 ? accumulated / electronCount : 0;
  return {
    isovalue,
    electronCount,
    enclosedFraction: fraction,
    actualFraction,
  };
}

/**
 * @param {Float32Array} values
 * @param {number} isovalue
 * @param {number[]} spacing
 * @returns {number}
 */
export function enclosedFractionAtIsovalue(values, isovalue, spacing) {
  const { electronCount, dV } = integratedElectronCount(values, spacing);
  if (electronCount <= 0) {
    return 0;
  }
  let enclosed = 0;
  for (let i = 0; i < values.length; i += 1) {
    if (values[i] >= isovalue) {
      enclosed += values[i] * dV;
    }
  }
  return enclosed / electronCount;
}
