import type { TFunction } from "i18next";
import type { VariantResult } from "../../api/types";
import { fmtInt, fmtNum } from "../../lib/format";

export function bareSoilMetrics(v: VariantResult): { days: number; exposure: number } | null {
  const days = v.bare_days_per_year;
  const exposure = v.exposure_index;
  if (days == null || exposure == null) return null;
  return { days, exposure };
}

export function anyBareSoilMetrics(variants: VariantResult[]): boolean {
  return variants.some((v) => bareSoilMetrics(v) !== null);
}

export function bareSoilLine(v: VariantResult, t: TFunction): string | null {
  const m = bareSoilMetrics(v);
  if (!m) return null;
  return t("planner.bare_soil_line", { days: fmtInt(m.days), exposure: fmtNum(m.exposure, 2) });
}