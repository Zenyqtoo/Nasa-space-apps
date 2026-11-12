const NBSP = " ";

export function fmtInt(v: number): string {
  const s = Math.round(Math.abs(v)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  return (v < 0 ? "−" : "") + s;
}

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = Math.abs(v).toFixed(digits).replace(".", ",");
  return (v < 0 ? "−" : "") + s;
}

export function fmtSigned(v: number): string {
  return (v > 0 ? "+" : v < 0 ? "−" : "") + fmtInt(Math.abs(v));
}
