import type { TFunction } from "i18next";
import type { VariantResult } from "../../api/types";
import { fmtNum } from "../../lib/format";

type LegacyBareSoil = {
  bare_days_per_year?: number | null;
  exposure_index?: number | null;
  mean_exposure?: number | null;
};

function bareSoilMetrics(v: VariantResult): { days: number; exposure: number } | null {
  let days = v.bare_days_per_year;
  let exposure = v.exposure_index;
  if (days == null || exposure == null) {
    const nested = (v as VariantResult & { bare_soil?: LegacyBareSoil }).bare_soil;
    if (nested) {
      if (days == null) days = nested.bare_days_per_year ?? null;
      if (exposure == null) exposure = nested.exposure_index ?? nested.mean_exposure ?? null;
    }
  }
  if (days == null || exposure == null) return null;
  return { days, exposure };
}

export function hasAnyBareSoilMetrics(variants: VariantResult[]): boolean {
  return variants.some((v) => bareSoilMetrics(v) !== null);
}

/** One-line bare-soil summary for rotation explanations when the API provides metrics. */
export function bareSoilLine(v: VariantResult, t: TFunction): string | null {
  const m = bareSoilMetrics(v);
  if (!m) return null;
  return t("planner.bare_soil_line", {
    days: Math.round(m.days),
    exposure: fmtNum(m.exposure, 2),
  });
}

export function bareSoilDaysCell(v: VariantResult): string {
  const m = bareSoilMetrics(v);
  return m ? fmtNum(Math.round(m.days), 0) : "—";
}

export function bareSoilExposureCell(v: VariantResult): string {
  const m = bareSoilMetrics(v);
  return m ? fmtNum(m.exposure, 2) : "—";
}