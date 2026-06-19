import { interpolateEnergy } from "../pes/interpolateEnergy.js";
import { drawEnergyPesChart } from "./EnergyPesChart.js";
import { drawEnergyLadder } from "./EnergyLadderChart.js";

/**
 * @param {number | null | undefined} value
 * @param {number} [digits]
 * @returns {string}
 */
function fmtHa(value, digits = 6) {
  return value != null && Number.isFinite(Number(value))
    ? `${Number(value).toFixed(digits)} Ha`
    : "—";
}

/**
 * @param {number | null | undefined} value
 * @returns {string}
 */
function fmtMha(value) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return `${(Number(value) * 1000).toFixed(2)} mHa`;
}

/**
 * @param {HTMLElement} dl
 * @param {Array<[string, string]>} rows
 */
function fillDl(dl, rows) {
  dl.replaceChildren();
  for (const [label, value] of rows) {
    const div = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    div.append(dt, dd);
    dl.appendChild(div);
  }
}

/**
 * @param {Record<string, unknown>} bundle
 * @param {{
 *   pesPoints: Array<{ bond_length: number, energy: number }> | null,
 *   previewBond: number,
 *   equilibriumBond: number,
 *   runMember: Record<string, unknown> | null,
 *   runLog: import("../runs/loadRunLog.js").RunLogSummary | null,
 * }} ctx
 */
export function updateEnergyTable(bundle, ctx) {
  const dl = document.getElementById("physics-energy-table");
  const note = document.getElementById("physics-energy-note");
  if (!dl) return;

  const refs = /** @type {Record<string, number> | undefined} */ (
    bundle.reference_energies
  );
  const hf = refs?.hf ?? null;
  const vqeBundle = Number(bundle.energy_hartree);
  const pes = ctx.pesPoints;
  const exactAtR =
    pes && pes.length > 0
      ? interpolateEnergy(pes, ctx.previewBond)
      : null;
  const exactAtR0 =
    pes && pes.length > 0
      ? interpolateEnergy(pes, ctx.equilibriumBond)
      : null;

  const runEnergy = ctx.runMember?.energy ?? ctx.runLog?.energy ?? null;
  const vqePrimary =
    runEnergy != null && Number.isFinite(Number(runEnergy))
      ? Number(runEnergy)
      : Number.isFinite(vqeBundle)
        ? vqeBundle
        : null;

  const deltaVqeHf =
    vqePrimary != null && hf != null ? vqePrimary - hf : null;
  const deltaVqeExact =
    vqePrimary != null && exactAtR != null ? vqePrimary - exactAtR : null;
  const correlation =
    exactAtR != null && hf != null ? exactAtR - hf : null;

  fillDl(dl, [
    ["Exact / FCI", fmtHa(exactAtR)],
    ["HF", fmtHa(hf)],
    ["VQE (bundle @ R₀)", fmtHa(vqeBundle)],
    ["VQE (selected)", fmtHa(runEnergy)],
    ["Δ(VQE − HF)", `${fmtHa(deltaVqeHf)} · ${fmtMha(deltaVqeHf)}`],
    ["Δ(VQE − exact)", `${fmtHa(deltaVqeExact)} · ${fmtMha(deltaVqeExact)}`],
    ["Correlation (exact − HF)", `${fmtHa(correlation)} · ${fmtMha(correlation)}`],
  ]);

  if (note) {
    const drift = Math.abs(ctx.previewBond - ctx.equilibriumBond) > 0.01;
    note.textContent = drift
      ? `Exact interpolated at R=${ctx.previewBond.toFixed(2)} Å; HF/VQE at R₀=${ctx.equilibriumBond.toFixed(2)} Å.`
      : `All energies at R=${ctx.previewBond.toFixed(2)} Å (equilibrium). HF from bundle reference.`;
  }
}

/**
 * @param {HTMLCanvasElement | null} canvas
 * @param {{
 *   exact?: number | null,
 *   hf?: number | null,
 *   vqe?: number | null,
 * }} levels
 */
export function updateEnergyLadder(canvas, levels) {
  if (!canvas) return;
  if (!canvas.offsetParent) return;
  drawEnergyLadder(canvas, levels);
}

/**
 * @param {HTMLCanvasElement | null} canvas
 * @param {Array<{ bond_length: number, energy: number }> | null} pesPoints
 * @param {number} previewBond
 * @param {{ equilibriumBond?: number }} refs
 */
export function updateEnergyPesChart(canvas, pesPoints, previewBond, refs) {
  if (!canvas || !pesPoints || pesPoints.length === 0) return;
  // Skip while the physics drawer is hidden — parent has no layout width yet.
  if (!canvas.offsetParent) return;
  drawEnergyPesChart(canvas, pesPoints, previewBond, refs);
}

/**
 * @param {import("../runs/loadRunLog.js").RunLogSummary | null} runLog
 */
export function updateRunProvenance(runLog) {
  const section = document.getElementById("physics-run-section");
  const dl = document.getElementById("physics-run-provenance");
  if (!section || !dl) return;

  if (!runLog) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  const finalIter =
    runLog.history.length > 0
      ? runLog.history[runLog.history.length - 1]
      : null;

  fillDl(dl, [
    ["Run ID", runLog.runId],
    ["Backend", runLog.backend ?? "—"],
    ["Mapper", runLog.mapper ?? "—"],
    [
      "2QR",
      runLog.twoQubitReduction != null
        ? String(runLog.twoQubitReduction)
        : "—",
    ],
    ["Shots", runLog.shots != null ? String(runLog.shots) : "—"],
    ["E (electronic)", fmtHa(runLog.electronicEnergy)],
    ["E (nuclear rep)", fmtHa(runLog.nuclearRepulsionEnergy)],
    ["E (total)", fmtHa(runLog.energy)],
    [
      "Optimizer",
      finalIter
        ? `${runLog.history.length} iter · final ${fmtHa(finalIter.energy)}`
        : "—",
    ],
    ["Timestamp", runLog.timestamp ?? "—"],
    [
      "Credits",
      runLog.costCredits != null ? String(runLog.costCredits) : "—",
    ],
  ]);
}

/**
 * @param {Record<string, unknown> | null | undefined} trajectories
 */
export function updateDynamicsSection(trajectories) {
  const dl = document.getElementById("physics-dynamics");
  const note = document.getElementById("physics-dynamics-note");
  if (!dl) return;

  if (!trajectories) {
    fillDl(dl, [["Status", "No trajectory metadata"]]);
    if (note) note.textContent = "";
    return;
  }

  const e0 = trajectories.E0;
  const e1 = trajectories.E1;
  const omega = trajectories.omega;
  const c0 = trajectories.c0;
  const c1 = trajectories.c1;
  const period = trajectories.period;
  const source = trajectories.source;

  fillDl(dl, [
    ["E₀", e0 != null ? fmtHa(Number(e0)) : "—"],
    ["E₁", e1 != null ? fmtHa(Number(e1)) : "—"],
    ["ω", omega != null ? `${Number(omega).toFixed(4)} a.u.` : "—"],
    ["c₀", c0 != null ? Number(c0).toFixed(4) : "—"],
    ["c₁", c1 != null ? Number(c1).toFixed(4) : "—"],
    ["Period", period != null ? `${Number(period).toFixed(3)} a.u.` : "—"],
    ["dt", trajectories.dt != null ? String(trajectories.dt) : "—"],
    ["Steps", trajectories.steps != null ? String(trajectories.steps) : "—"],
    ["Source", source != null ? String(source) : "—"],
  ]);

  if (note) {
    const src = String(source ?? "");
    if (src.includes("superposition") || src.includes("hardware")) {
      note.textContent =
        "Two-state superposition drives time-dependent Bohmian trajectories.";
    } else if (src === "exact_diag") {
      note.textContent = "Exact two-state superposition reference dynamics.";
    } else {
      note.textContent = "Bohmian velocity field from bundle trajectory metadata.";
    }
  }
}

/**
 * @param {Array<{ backend?: string | null, energy?: number | null }>} members
 * @param {number | null} exactAtR0
 * @param {(backend: string | null | undefined) => boolean} isHardware
 */
export function updateHardwareTable(members, exactAtR0, isHardware) {
  const section = document.getElementById("physics-hardware-section");
  const tbody = document.querySelector("#physics-hardware-table tbody");
  if (!section || !tbody) return;

  if (!members.length) {
    section.hidden = true;
    return;
  }

  /** @type {Map<string, number[]>} */
  const byBackend = new Map();
  for (const member of members) {
    const key = String(member.backend ?? "unknown");
    const e = Number(member.energy);
    if (!Number.isFinite(e)) continue;
    const list = byBackend.get(key) ?? [];
    list.push(e);
    byBackend.set(key, list);
  }

  if (byBackend.size === 0) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  tbody.replaceChildren();

  for (const [backend, energies] of [...byBackend.entries()].sort((a, b) =>
    a[0].localeCompare(b[0]),
  )) {
    const mean = energies.reduce((s, v) => s + v, 0) / energies.length;
    const variance =
      energies.reduce((s, v) => s + (v - mean) ** 2, 0) / energies.length;
    const std = Math.sqrt(variance);
    const deltaMha =
      exactAtR0 != null && Number.isFinite(exactAtR0)
        ? ((mean - exactAtR0) * 1000).toFixed(2)
        : "—";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${backend}${isHardware(backend) ? "" : ""}</td>
      <td>${energies.length}</td>
      <td>${mean.toFixed(5)}</td>
      <td>${std.toFixed(5)}</td>
      <td>${deltaMha}</td>
    `;
    tbody.appendChild(tr);
  }
}

/**
 * @param {Record<string, unknown>} bundle
 */
export function updateGridSection(bundle) {
  const dl = document.getElementById("physics-grid");
  if (!dl) return;

  const density = /** @type {Record<string, unknown> | undefined} */ (
    bundle.density
  );
  const backend = bundle.backend
    ? /** @type {Record<string, string>} */ (bundle.backend)
    : null;
  const spacing = density?.spacing
    ? /** @type {number[]} */ (density.spacing).map((v) => v.toFixed(3)).join(" × ")
    : "—";
  const shape = density?.shape
    ? /** @type {number[]} */ (density.shape).join(" × ")
    : "—";

  fillDl(dl, [
    ["Method", String(bundle.method ?? "—")],
    [
      "Backend",
      backend ? `${backend.provider} / ${backend.name}` : "—",
    ],
    ["Density kind", String(density?.kind ?? "—")],
    ["Grid spacing (Å)", spacing],
    ["Grid shape", shape],
    [
      "∫ρ (e⁻)",
      density?.electron_count != null
        ? Number(density.electron_count).toFixed(3)
        : "—",
    ],
    [
      "Default isovalue",
      density?.default_isovalue != null
        ? String(density.default_isovalue)
        : "—",
    ],
  ]);
}

/**
 * Refresh all physics panel sections.
 *
 * @param {Record<string, unknown>} bundle
 * @param {{
 *   pesPoints: Array<{ bond_length: number, energy: number }> | null,
 *   previewBond: number,
 *   equilibriumBond: number,
 *   runMember: Record<string, unknown> | null,
 *   runLog: import("../runs/loadRunLog.js").RunLogSummary | null,
 *   ensembleMembers: Array<{ backend?: string | null, energy?: number | null }>,
 *   isHardwareBackend: (backend: string | null | undefined) => boolean,
 *   pesChart: HTMLCanvasElement | null,
 *   energyLadder: HTMLCanvasElement | null,
 * }} ctx
 */
export function updatePhysicsPanel(bundle, ctx) {
  const refs = /** @type {Record<string, number> | undefined} */ (
    bundle.reference_energies
  );
  const hf = refs?.hf ?? null;
  const vqeBundle = Number(bundle.energy_hartree);

  const exactAtR =
    ctx.pesPoints && ctx.pesPoints.length > 0
      ? interpolateEnergy(ctx.pesPoints, ctx.previewBond)
      : null;
  const runEnergy = ctx.runMember?.energy ?? ctx.runLog?.energy ?? null;
  const vqePrimary =
    runEnergy != null && Number.isFinite(Number(runEnergy))
      ? Number(runEnergy)
      : Number.isFinite(vqeBundle)
        ? vqeBundle
        : null;

  updateEnergyTable(bundle, ctx);
  updateEnergyLadder(ctx.energyLadder, {
    exact: exactAtR,
    hf,
    vqe: vqePrimary,
  });

  const ladderNote = document.getElementById("physics-ladder-note");
  if (ladderNote) {
    const drift = Math.abs(ctx.previewBond - ctx.equilibriumBond) > 0.01;
    ladderNote.textContent = drift
      ? `Exact at R=${ctx.previewBond.toFixed(2)} Å; HF/VQE at R₀=${ctx.equilibriumBond.toFixed(2)} Å.`
      : `All levels at R=${ctx.previewBond.toFixed(2)} Å · mHa gaps bracketed left`;
  }

  updateEnergyPesChart(ctx.pesChart, ctx.pesPoints, ctx.previewBond, {
    equilibriumBond: ctx.equilibriumBond,
  });
  updateRunProvenance(ctx.runLog);
  updateDynamicsSection(
    /** @type {Record<string, unknown> | undefined} */ (bundle.trajectories),
  );

  const exactAtR0 =
    ctx.pesPoints && ctx.pesPoints.length > 0
      ? interpolateEnergy(ctx.pesPoints, ctx.equilibriumBond)
      : null;
  updateHardwareTable(
    ctx.ensembleMembers,
    exactAtR0,
    ctx.isHardwareBackend,
  );
  updateGridSection(bundle);
}
