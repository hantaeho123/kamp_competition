"""charts/specs.json의 막대 차트를 발표자료 색·글꼴에 맞춘 PNG로 그린다."""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
here = os.path.dirname(os.path.abspath(__file__))
for f in ["NanumGothic", "AppleGothic", "Malgun Gothic"]:
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f; break
plt.rcParams["axes.unicode_minus"] = False
INK, MUTED, GRID = "#2B2D42", "#8D99AE", "#DDE3EC"
FMT = {"0.00": "{:.2f}", "0.0": "{:.1f}", "0": "{:.0f}"}
for sp in json.load(open(os.path.join(here, "charts", "specs.json"))):
    cats, series = sp["cats"], sp["series"]
    n, k = len(cats), len(series)
    fig, ax = plt.subplots(figsize=(sp["w"], sp["h"]), dpi=220)
    colors = ["#" + c for c in sp["colors"]]
    f = FMT.get(sp["fmt"], "{:.2f}")
    bw = 0.72 / k
    horiz = sp["dir"] == "bar"
    allv = [v for s_ in series for v in s_["values"]]
    lo = sp["min"] if sp.get("min") is not None else 0
    hi = sp["max"] if sp.get("max") is not None else max(allv) * 1.13
    for j, s_ in enumerate(series):
        pos = [i + (j - (k - 1) / 2) * bw for i in range(n)]
        col = colors[j % len(colors)]
        if horiz:
            ax.barh(pos, [v - lo for v in s_["values"]], bw * 0.92, left=lo, color=col, label=s_["name"])
            for p, v in zip(pos, s_["values"]):
                ax.text(v + (hi - lo) * 0.01, p, f.format(v), va="center", ha="left", fontsize=10, color=INK)
        else:
            ax.bar(pos, [v - lo for v in s_["values"]], bw * 0.92, bottom=lo, color=col, label=s_["name"])
            for p, v in zip(pos, s_["values"]):
                ax.text(p, v + (hi - lo) * 0.012, f.format(v), va="bottom", ha="center", fontsize=10, color=INK)
    if horiz:
        ax.set_yticks(range(n), cats, fontsize=10.5, color=INK); ax.invert_yaxis(); ax.set_xlim(lo, hi)
        ax.xaxis.grid(True, color=GRID, lw=0.7); ax.tick_params(axis="x", labelsize=9, colors=MUTED)
    else:
        ax.set_xticks(range(n), [c.replace("(", "\n(") for c in cats], fontsize=10, color=INK); ax.set_ylim(lo, hi)
        ax.yaxis.grid(True, color=GRID, lw=0.7); ax.tick_params(axis="y", labelsize=9, colors=MUTED)
    ax.set_axisbelow(True)
    for sd in ("top", "right"): ax.spines[sd].set_visible(False)
    for sd in ("left", "bottom"): ax.spines[sd].set_color(GRID)
    ax.tick_params(length=0)
    if sp["title"]:
        ax.set_title(sp["title"], fontsize=12.5, color="#14213D", fontweight="bold", loc="left", pad=10)
    if k > 1:
        ax.legend(frameon=False, fontsize=10, loc="upper center", bbox_to_anchor=(0.5, -0.06 if horiz else -0.16), ncol=k, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(here, "charts", f"chart_{sp['id']}.png"), facecolor="white")
    plt.close(fig)
print("charts rendered")
