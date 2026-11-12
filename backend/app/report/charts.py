"""Графики для PDF-плана (matplotlib, без дисплея)."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from .fonts import FONT_BOLD_PATH, FONT_PATH  # noqa: E402

for _p in (FONT_PATH, FONT_BOLD_PATH):
    font_manager.fontManager.addfont(str(_p))
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False

# Палитра, различимая при печати в оттенках серого и при дальтонизме (Okabe–Ito)
COLORS = ["#555555", "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]
MARKERS = ["o", "s", "^", "D", "v", "P"]


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def forecast_chart(variants: list[dict], labels: list[str], t: dict[str, str]) -> bytes:
    """Доход и индекс почвы по годам для всех вариантов."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.3))
    for i, (v, label) in enumerate(zip(variants, labels)):
        years = [y["year"] for y in v["years"]]
        style = {"color": COLORS[i % len(COLORS)], "marker": MARKERS[i % len(MARKERS)], "linewidth": 1.8, "markersize": 5}
        ax1.plot(years, [y["income_kzt_ha"] / 1000 for y in v["years"]], label=label, **style)
        ax2.plot(years, [y["soil_index"] for y in v["years"]], label=label, **style)
    for ax, title in ((ax1, t["chart_income"]), (ax2, t["chart_soil"])):
        ax.set_title(title, fontsize=10)
        ax.set_xlabel(t["chart_year"], fontsize=9)
        ax.set_xticks([y["year"] for y in variants[0]["years"]])
        ax.grid(True, color="#dddddd", linewidth=0.6)
        ax.tick_params(labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    ax1.axhline(0, color="#999999", linewidth=0.8)
    fig.legend(*ax1.get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=8, frameon=False, bbox_to_anchor=(0.5, -0.16))
    fig.tight_layout()
    return _png(fig)


def stress_chart(variants: list[dict], labels: list[str], year_indexes: list[int], t: dict[str, str]) -> bytes:
    """Доход за план: обычные годы против засухи в выбранный год."""
    fig, ax = plt.subplots(figsize=(9.2, 2.9))
    n = len(variants)
    width = 0.38
    normal = [v["stress"]["total_normal_kzt_ha"] / 1000 for v in variants]
    dry = [v["stress"]["per_year"][i - 1]["total_if_dry_kzt_ha"] / 1000 for v, i in zip(variants, year_indexes)]
    xs = range(n)
    ax.bar([x - width / 2 for x in xs], normal, width, label=t["chart_normal"], color="#4a7c3a")
    ax.bar([x + width / 2 for x in xs], dry, width, label=t["chart_dry"], color="#c9772b", hatch="//", edgecolor="white")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel(t["chart_income"], fontsize=9)
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.grid(True, axis="y", color="#dddddd", linewidth=0.6)
    ax.tick_params(labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    return _png(fig)
