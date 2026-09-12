import os
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("GH_USERNAME", "hir-al-14")

HEADERS_GQL = {"Authorization": f"Bearer {TOKEN}"}
HEADERS_REST = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

LINE = "#9D4EDD"
MARK = "#C77DFF"
TEXT = "#D8C9E8"
GRID = "#3C2A52"
BORDER = "#9D4EDD"

# Recognizable per-language colors (GitHub linguist-style), with a fallback cycle.
LANGUAGE_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B", "Go": "#00ADD8", "Rust": "#dea584",
    "Swift": "#F05138", "Kotlin": "#A97BFF", "Dart": "#00B4AB",
}
FALLBACK_CYCLE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2", "#937860"]

os.makedirs("assets", exist_ok=True)


def style_transparent(fig, ax):
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")


def add_border(ax):
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(BORDER)
        spine.set_linewidth(1.2)


# ---------- 1. Monthly contributions line graph ----------

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

resp = requests.post(
    "https://api.github.com/graphql",
    json={"query": QUERY, "variables": {"login": USERNAME}},
    headers=HEADERS_GQL,
    timeout=30,
)
resp.raise_for_status()
collection = resp.json()["data"]["user"]["contributionsCollection"]
weeks = collection["contributionCalendar"]["weeks"]

monthly = defaultdict(int)
for week in weeks:
    for day in week["contributionDays"]:
        date = datetime.strptime(day["date"], "%Y-%m-%d")
        monthly[(date.year, date.month)] += day["contributionCount"]

today = datetime.utcnow()
keys = sorted(k for k in monthly if k != (today.year, today.month))

seen_month_names = defaultdict(int)
for year, month in keys:
    seen_month_names[datetime(year, month, 1).strftime("%b")] += 1

labels, counts = [], []
for year, month in keys:
    base_label = datetime(year, month, 1).strftime("%b")
    label = f"{base_label} '{str(year)[2:]}" if seen_month_names[base_label] > 1 else base_label
    labels.append(label)
    counts.append(monthly[(year, month)])

fig, ax = plt.subplots(figsize=(6.5, 2.6), dpi=150)
style_transparent(fig, ax)

x = range(len(labels))
ax.plot(x, counts, color=LINE, linewidth=2.5, marker="o", markersize=5,
        markerfacecolor=MARK, markeredgecolor=MARK, zorder=3)
ax.fill_between(x, counts, color=MARK, alpha=0.15, zorder=1)
ax.set_xticks(list(x))
ax.set_xticklabels(labels)

add_border(ax)
ax.tick_params(colors=TEXT, labelsize=9)
ax.set_title(f"{USERNAME}'s Monthly Contributions", color=TEXT, fontsize=11.5,
             fontweight="bold", pad=10)
ax.grid(axis="y", color=GRID, linewidth=0.7, zorder=0)

plt.subplots_adjust(left=0.08, right=0.97, top=0.86, bottom=0.14)
plt.savefig("assets/monthly-commits.svg", format="svg", transparent=True)
plt.close(fig)
print("Saved assets/monthly-commits.svg")


# ---------- 2. Stats card (commits / PRs / issues / repos) ----------

stats = [
    ("Commits", collection["totalCommitContributions"]),
    ("Pull Requests", collection["totalPullRequestContributions"]),
    ("Issues", collection["totalIssueContributions"]),
    ("Repos contributed to", collection["totalRepositoryContributions"]),
]

fig, ax = plt.subplots(figsize=(6.5, 1.8), dpi=150)
style_transparent(fig, ax)
ax.axis("off")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
fig.subplots_adjust(left=0.02, right=0.98, top=0.96, bottom=0.04)
ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                            edgecolor=BORDER, linewidth=1.2))

n = len(stats)
for i, (label, value) in enumerate(stats):
    cx = (i + 0.5) / n
    ax.text(cx, 0.60, str(value), transform=ax.transAxes, ha="center", va="center",
            fontsize=24, fontweight="bold", color=MARK)
    ax.text(cx, 0.26, label, transform=ax.transAxes, ha="center", va="center",
            fontsize=9.5, color=TEXT)
    if i > 0:
        ax.axvline(i / n, color=GRID, linewidth=1, ymin=0.14, ymax=0.86)

fig.text(0.5, 0.88, f"{USERNAME}'s Activity (past year)", ha="center", va="center",
          fontsize=11.5, fontweight="bold", color=TEXT)
plt.savefig("assets/stats.svg", format="svg", transparent=True)
plt.close(fig)
print("Saved assets/stats.svg")


# ---------- 3. Languages: single segmented bar + legend ----------

repos_resp = requests.get(
    f"https://api.github.com/users/{USERNAME}/repos",
    headers=HEADERS_REST,
    params={"per_page": 100, "type": "owner"},
    timeout=30,
)
repos_resp.raise_for_status()
repos = [r for r in repos_resp.json() if not r["fork"]]

lang_totals = defaultdict(int)
for repo in repos:
    lang_resp = requests.get(repo["languages_url"], headers=HEADERS_REST, timeout=30)
    if lang_resp.ok:
        for lang, byte_count in lang_resp.json().items():
            lang_totals[lang] += byte_count

top_langs = sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
total_bytes = sum(v for _, v in top_langs) or 1
lang_names = [k for k, _ in top_langs]
lang_pcts = [100 * v / total_bytes for _, v in top_langs]
colors = [LANGUAGE_COLORS.get(name, FALLBACK_CYCLE[i % len(FALLBACK_CYCLE)])
          for i, name in enumerate(lang_names)]

fig, ax = plt.subplots(figsize=(6.5, 2.2), dpi=150)
style_transparent(fig, ax)
ax.axis("off")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
fig.subplots_adjust(left=0.03, right=0.97, top=0.94, bottom=0.05)
ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                            edgecolor=BORDER, linewidth=1.2))

fig.text(0.5, 0.88, f"{USERNAME}'s Most Used Languages", ha="center", va="center",
          fontsize=11.5, fontweight="bold", color=TEXT)

# Segmented pill bar
bar_y, bar_h = 0.70, 0.10
left = 0.06
bar_width = 0.88
cursor = left
for pct, color in zip(lang_pcts, colors):
    w = bar_width * (pct / 100)
    ax.add_patch(plt.Rectangle((cursor, bar_y), w, bar_h, transform=ax.transAxes,
                                facecolor=color, edgecolor="none"))
    cursor += w

# Two-column legend below
rows = (len(lang_names) + 1) // 2
col_x = [0.08, 0.55]
row_start_y = 0.48
row_gap = 0.19
for i, (name, pct, color) in enumerate(zip(lang_names, lang_pcts, colors)):
    col = i // rows
    row = i % rows
    x = col_x[col]
    y = row_start_y - row * row_gap
    ax.add_patch(plt.Circle((x, y), 0.014, transform=ax.transAxes, facecolor=color, edgecolor="none"))
    ax.text(x + 0.03, y, f"{name}  {pct:.2f}%", transform=ax.transAxes,
            ha="left", va="center", fontsize=9.5, color=TEXT)

plt.savefig("assets/languages.svg", format="svg", transparent=True)
plt.close(fig)
print("Saved assets/languages.svg")