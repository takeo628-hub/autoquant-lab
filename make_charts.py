"""Generate article charts for Zenn (light 'card' PNGs, readable in dark mode too).

Palette validated with the dataviz validator (categorical indigo/amber,
worst adjacent CVD dE 33.8). Every value is direct-labeled so identity is
never carried by color alone, and the articles also carry the data tables.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

OUT = r"C:\Users\yukur\zenn-content\images"
os.makedirs(OUT, exist_ok=True)

INDIGO, AMBER, RED, INK, SUB, LINE = "#4338ca", "#d97706", "#b91c1c", "#17181c", "#5b616e", "#e6e8ec"
SURFACE = "#fcfcfb"

names = {f.name for f in fm.fontManager.ttflist}
for cand in ("Yu Gothic", "Meiryo", "MS Gothic", "Yu Gothic UI"):
    if cand in names:
        plt.rcParams["font.family"] = cand
        print("font:", cand)
        break
else:
    print("WARNING: no Japanese font found")
plt.rcParams.update({"axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
                     "text.color": INK, "axes.labelcolor": SUB,
                     "xtick.color": SUB, "ytick.color": SUB, "axes.edgecolor": LINE,
                     "savefig.facecolor": SURFACE, "font.size": 12})


def style(ax, xlabel=""):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis="x", color=LINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)          # no stray dashes beside labels
    ax.tick_params(axis="x", length=3, color=LINE)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11)


# ---------------------------------------------- 1. backtest vs reality
fig, ax = plt.subplots(figsize=(8, 2.9), dpi=170)
labels = ["バックテスト\n（過去データ上）", "実運用\n（仮想売買 119件）"]
vals = [359.9, -8.0]
bars = ax.barh(labels, vals, color=[INDIGO, RED], height=0.5, zorder=3)
for b, v in zip(bars, vals):
    ax.text(v + (12 if v > 0 else -12), b.get_y() + b.get_height() / 2,
            f"{v:+.1f}%", va="center", ha="left" if v > 0 else "right",
            fontweight="bold", fontsize=14, color=INDIGO if v > 0 else RED)
ax.axvline(0, color=SUB, linewidth=1, zorder=4)
ax.set_xlim(-90, 430)
ax.set_title("同じ戦略の「年率リターン」— 過去データ上と実運用", fontsize=13,
             fontweight="bold", loc="left", pad=12)
style(ax, "年率リターン（%）")
ax.invert_yaxis()
fig.tight_layout()
fig.savefig(os.path.join(OUT, "backtest-vs-reality.png"), bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------- 2. overnight vs intraday
assets = ["日経レバETF\n(1570)", "TOPIX ETF\n(1306)", "SPY\n(米S&P500)", "QQQ\n(米ナスダック100)"]
intraday = [-53, -49, 90, 15]
overnight = [3067, 35, 386, 1166]
fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.4), dpi=170)
for ax, vals, color, ttl in ((axes[0], intraday, AMBER, "日中だけ保有（寄付→引け）"),
                            (axes[1], overnight, INDIGO, "夜間だけ保有（引け→翌朝の寄付）")):
    bars = ax.barh(assets, vals, color=color, height=0.5, zorder=3)
    span = max(abs(min(vals)), abs(max(vals)))
    for b, v in zip(bars, vals):
        ax.text(v + (span * 0.03 if v >= 0 else -span * 0.03),
                b.get_y() + b.get_height() / 2, f"{v:+,}%", va="center",
                ha="left" if v >= 0 else "right", fontsize=11, fontweight="bold", color=color)
    ax.axvline(0, color=SUB, linewidth=1, zorder=4)
    lo = min(vals) * 1.9 if min(vals) < 0 else -span * 0.06
    ax.set_xlim(lo, max(vals) * 1.28)
    ax.set_title(ttl, fontsize=12, fontweight="bold", loc="left", pad=10, color=color)
    style(ax, "累積リターン（%）")
    ax.invert_yaxis()
axes[1].set_yticklabels([])
fig.suptitle("株のリターンはどこで生まれているか（各銘柄の全履歴・累積）",
             fontsize=13, fontweight="bold", x=0.01, ha="left", y=1.06)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "overnight-vs-intraday.png"), bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------- 3. bootstrap distribution
fig, ax = plt.subplots(figsize=(8.4, 2.6), dpi=170)
p5, p25, p50, p75, p95 = 18.8, 26.5, 31.6, 37.7, 46.8
ax.plot([p5, p95], [0, 0], color=INDIGO, linewidth=3, alpha=0.35,
        solid_capstyle="round", zorder=3)
ax.plot([p25, p75], [0, 0], color=INDIGO, linewidth=11,
        solid_capstyle="round", zorder=4)
ax.plot([p50], [0], "o", color=SURFACE, markersize=13, zorder=5)
ax.plot([p50], [0], "o", color=INDIGO, markersize=9, zorder=6)
for x, t, dy in ((p5, f"悲観5%\n+{p5}%", -0.45), (p50, f"中央値\n+{p50}%", 0.34),
                 (p95, f"楽観95%\n+{p95}%", -0.45)):
    ax.text(x, dy, t, ha="center", va="center", fontsize=11,
            fontweight="bold", color=INDIGO)
ax.plot([24.1, 24.1], [-0.10, 0.10], color=RED, linewidth=3,
        solid_capstyle="round", zorder=7)
ax.text(23.2, 0.40, "市場平均(QQQ)\n+24.1%", ha="center", va="center",
        fontsize=10.5, fontweight="bold", color=RED)
ax.set_ylim(-0.7, 0.62)
ax.set_xlim(14, 51)
ax.set_yticks([])
ax.set_title("同じ戦略でも「歴史の順番」が変わると年率はここまで散らばる\n"
             "（21日ブロック・ブートストラップ 1,000通り）",
             fontsize=13, fontweight="bold", loc="left", pad=14)
style(ax, "15.6年の年率リターン（%）")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "bootstrap-distribution.png"), bbox_inches="tight")
plt.close(fig)

for f in sorted(os.listdir(OUT)):
    print("saved:", f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")
