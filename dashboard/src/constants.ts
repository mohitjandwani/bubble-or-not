import type { Factor, Lamp } from "./types";

/** Mirrors config/weights.yaml — display metadata the SPA needs but /state
 * doesn't repeat per-signature (factor names/descriptions/weights are static). */
export const FACTOR_ORDER: Factor[] = ["f1", "f2", "f3", "f4", "f5"];

export const FACTOR_WEIGHTS: Record<Factor, number> = {
  f1: 0.25,
  f2: 0.2,
  f3: 0.2,
  f4: 0.15,
  f5: 0.2,
  f6: 0,
};

export const FACTOR_NAMES: Record<Factor, string> = {
  f1: "Liquidity",
  f2: "Bellwethers",
  f3: "Circular financing",
  f4: "Insiders",
  f5: "Breadth",
  f6: "Narrative temp",
};

export const FACTOR_DESCRIPTIONS: Record<Factor, string> = {
  f1: "Forward-looking tightening pressure — implied path, rhetoric, real rates",
  f2: "Forward earnings picture for the 8-name bellwether universe",
  f3: "Revenue funded by your own capital, measured against balance-sheet size",
  f4: "Insider supply — mega-sales, sell/buy ratio, lockup overhang",
  f5: "Pure quant — concentration, cap-vs-equal-weight, participation",
  f6: "Hype-language density vs the cited 1999 press baseline",
};

export const BTI_ZONES = { calm: [0, 40], elevated: [40, 70], danger: [70, 100] } as const;

export function zoneColor(score: number | null | undefined): string {
  if (score == null) return "var(--gray)";
  if (score < 40) return "var(--green)";
  if (score < 70) return "var(--amber)";
  return "var(--red)";
}

export function lampColor(lamp: Lamp): string {
  switch (lamp) {
    case "fired":
      return "var(--red)";
    case "partial":
      return "var(--yellow)";
    case "watch":
      return "var(--gray)";
    case "no_data":
      return "var(--dim)";
    case "not":
    default:
      return "var(--gray)";
  }
}

export function confidenceColor(c: "high" | "medium" | "low"): string {
  if (c === "high") return "var(--green)";
  if (c === "medium") return "var(--yellow)";
  return "var(--red)";
}
