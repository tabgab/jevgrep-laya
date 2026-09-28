"""Build the Laya vs OpenJev summary report: SVG charts + HTML, printed to PDF by headless Chrome."""
import json, os
import matplotlib
matplotlib.use("svg")
import matplotlib.pyplot as plt

BASE = "/Users/gabortabi/DEV/JevGrep_Using_Laya"
OUT = os.path.join(BASE, "report")
EVAL = os.path.join(BASE, "eval")
TOOLS = os.path.join(BASE, "tooleval")

# Reference palette (light mode): categorical slots 1-2, neutral for baselines, text tokens.
OPENJEV, LAYA, LAYA_LIGHT, GRAY, GRAY_LIGHT = "#2a78d6", "#eb6834", "#f4a582", "#8a8984", "#c9c8c3"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
plt.rcParams.update({
    "font.family": "Helvetica", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "axes.spines.top": False,
    "axes.spines.right": False, "axes.spines.left": False, "svg.fonttype": "none",
})


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight", transparent=True)
    plt.close(fig)


def bar_label(ax, bars, fmt, pad: float = 3):
    for b in bars:
        v = b.get_width()
        ax.text(v + pad, b.get_y() + b.get_height() / 2, fmt(v), va="center", fontsize=9, color=INK)


# ---------- Stage A: file relevance on jevgrep's own question ----------
laya_a = json.load(open(os.path.join(EVAL, "stageA.json")))
open_a = json.load(open(os.path.join(EVAL, "stageA.openjev.json")))
groups = [("gold", "Files the fix or its tests changed (27)"), ("sibling", "Other files, same folders (87)"),
          ("random", "Random files (100)")]


def admitted(rows, label):
    v = [r["single"] for r in rows if r["label"] == label]
    return 100 * sum(x > 0.25 for x in v) / len(v)


fig, ax = plt.subplots(figsize=(6.6, 2.5))
ys = range(len(groups))
h = 0.36
b1 = ax.barh([y - h / 2 for y in ys], [admitted(laya_a, g) for g, _ in groups], h, color=LAYA, label="Laya")
b2 = ax.barh([y + h / 2 for y in ys], [admitted(open_a, g) for g, _ in groups], h, color=OPENJEV, label="OpenJev")
bar_label(ax, b1, lambda v: f"{v:.0f}%")
bar_label(ax, b2, lambda v: f"{v:.0f}%")
ax.set_yticks(list(ys), [n for _, n in groups])
ax.invert_yaxis()
ax.set_xlim(0, 112)
ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
ax.xaxis.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.tick_params(length=0)
ax.set_xlabel("Share of files jevgrep keeps (score > 0.25)")
ax.legend(frameon=False, loc="lower right", ncol=2, bbox_to_anchor=(1, 1.0))
save(fig, "fig_admit.svg")


def auc(pos, neg):
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


tasks = []
for r in laya_a:
    if r["task"] not in tasks:
        tasks.append(r["task"])


def per_task(rows):
    out = []
    for t in tasks:
        g = [r["single"] for r in rows if r["task"] == t and r["label"] == "gold"]
        n = [r["single"] for r in rows if r["task"] == t and r["label"] != "gold"]
        out.append(auc(g, n))
    return out


fig, ax = plt.subplots(figsize=(6.6, 3.0))
names = [t.split("__")[0].replace("-dev", "").replace("-doc", "") for t in tasks]
xs = range(len(tasks))
ax.axhline(0.5, color=GRAY, lw=1, ls=(0, (3, 3)))
ax.text(-0.4, 0.515, "chance", color=INK2, fontsize=8, ha="left")
ax.scatter(xs, per_task(laya_a), s=46, color=LAYA, edgecolor="white", lw=1.5, zorder=3, label="Laya")
ax.scatter(xs, per_task(open_a), s=46, color=OPENJEV, edgecolor="white", lw=1.5, zorder=3, label="OpenJev")
ax.set_xticks(list(xs), names, rotation=35, ha="right")
ax.set_ylim(0.2, 1.05)
ax.set_ylabel("AUC: fix files vs other files")
ax.yaxis.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.tick_params(length=0)
ax.legend(frameon=False, loc="lower right", ncol=2, bbox_to_anchor=(1, 1.0))
save(fig, "fig_auc.svg")

pooled = {}
for name, rows in (("laya", laya_a), ("openjev", open_a)):
    g = [r["single"] for r in rows if r["label"] == "gold"]
    pooled[name] = {lab: auc(g, [r["single"] for r in rows if r["label"] == lab]) for lab in ("sibling", "random")}

# ---------- Stage B: full jg search on psf/requests ----------
fig, ax = plt.subplots(figsize=(3.2, 2.2))
labels = ["Laya", "OpenJev", "Jev\n(recorded)"]
files = [76, 5, 6]
bars = ax.barh(labels, files, 0.55, color=[LAYA, OPENJEV, GRAY])
bar_label(ax, bars, lambda v: f"{v:.0f}", pad=1.5)
ax.invert_yaxis()
ax.set_xlim(0, 90)
ax.set_xlabel("Files returned (repo has 113)")
ax.xaxis.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.tick_params(length=0)
save(fig, "fig_files.svg")

fig, ax = plt.subplots(figsize=(3.2, 2.2))
kb = [391.452, 9.413, 6.880]
bars = ax.barh(labels, kb, 0.55, color=[LAYA, OPENJEV, GRAY])
for b, v in zip(bars, kb):
    ax.text(v * 1.15, b.get_y() + b.get_height() / 2, f"{v:,.0f} KB" if v > 100 else f"{v:.1f} KB",
            va="center", fontsize=9)
ax.set_xscale("log")
ax.set_xlim(1, 3000)
ax.set_xticks([1, 10, 100, 1000], ["1 KB", "10 KB", "100 KB", "1 MB"])
ax.minorticks_off()
ax.invert_yaxis()
ax.set_xlabel("Output handed to the agent (log scale)")
ax.xaxis.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.tick_params(length=0)
save(fig, "fig_size.svg")

# ---------- Tool selection ----------
tool = json.load(open(os.path.join(TOOLS, "summary.json")))
arms = [("laya", "Laya (English, as routed)", LAYA), ("laya-multilingual", "Laya (multilingual)", LAYA_LIGHT),
        ("openjev", "OpenJev", OPENJEV), ("bm25", "Keyword search (BM25)", GRAY_LIGHT)]
fig, ax = plt.subplots(figsize=(6.6, 2.9))
ks = ["top1", "top3", "top5"]
w = 0.19
for i, (key, label, color) in enumerate(arms):
    vals = [100 * tool[key][k] for k in ks]
    xs = [j + (i - 1.5) * w for j in range(len(ks))]
    bars = ax.bar(xs, vals, w * 0.9, color=color, label=label)
    for x, v in zip(xs, vals):
        ax.text(x, v + 1.2, f"{v:.1f}".removesuffix(".0"), ha="center", fontsize=7.5, color=INK)
for j, k in enumerate(ks):
    r = 100 * tool["random"][k]
    ax.plot([j - 2 * w, j + 2 * w], [r, r], color=INK2, lw=1, ls=(0, (3, 2)))
    ax.text(j + 2 * w + 0.02, r, "random", fontsize=7.5, color=INK2, va="center")
ax.set_xticks(range(len(ks)), ["Right tool ranked 1st", "Right tool in top 3", "Right tool in top 5"])
ax.set_ylim(0, 116)
ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
ax.yaxis.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.tick_params(length=0)
ax.legend(frameon=False, ncol=4, loc="lower left", bbox_to_anchor=(0, 1.02), fontsize=8.5)
save(fig, "fig_tools.svg")

data = {"pooled": pooled, "tool": tool}
json.dump(data, open(os.path.join(OUT, "numbers.json"), "w"), indent=1)
print(json.dumps(data, indent=1))
