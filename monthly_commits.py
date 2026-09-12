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

BG = "#F7F0FB"
LINE = "#7B2CBF"
MARK = "#9D4EDD"
TEXT = "#4A3F55"
GRID = "#E4D4F4"
PALETTE = ["#7B2CBF", "#9D4EDD", "#C77DFF", "#B084CC", "#5A189A", "#D9BBF9", "#8672A0"]

os.makedirs("assets", exist_ok=True)


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

# Group by (year, month) so two different Septembers never collide.
monthly = defaultdict(int)
for week in weeks:
    for day in week["contributionDays"]:
        date = datetime.strptime(day["date"], "%Y-%m-%d")
        monthly[(date.year, date.month)] += day["contributionCount"]

# Drop the current, still-incomplete month so it doesn't skew the shape.
today = datetime.utcnow()
keys = sorted(k for k in monthly if k != (today.year, today.month))

labels = []
counts = []
seen_month_names = defaultdict(int)
for year, month in keys:
    seen_month_names[datetime(year, month, 1).strftime("%b")] += 1

for year, month in keys:
    base_label = datetime(year, month, 1).strftime("%b")
    label = f"{base_label} '{str(year)[2:]}" if seen_month_names[base_label] > 1 else base_label
    labels.append(label)
    counts.append(monthly[(year, month)])

fig, ax = plt.subplots(figsize=(9, 3), dpi=150)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

x = range(len(labels))
ax.plot(x, counts, color=LINE, linewidth=2.5, marker="o", markersize=5,
        markerfacecolor=MARK, markeredgecolor=MARK, zorder=3)
ax.fill_between(x, counts, color=MARK, alpha=0.15, zorder=1)
ax.set_xticks(list(x))
ax.set_xticklabels(labels)

for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color("#C9A9E0")
ax.tick_params(colors=TEXT, labelsize=9)
ax.set_title(f"{USERNAME}'s Monthly Contributions", color=TEXT, fontsize=12,
             fontweight="bold", pad=12)
ax.grid(axis="y", color=GRID, linewidth=0.7, zorder=0)

plt.tight_layout()
plt.savefig("assets/monthly-commits.svg", format="svg")
plt.close(fig)
print("Saved assets/monthly-commits.svg")


# ---------- 2. Stats card (commits / PRs / issues / repos) ----------

stats = [
    ("Commits", collection["totalCommitContributions"]),
    ("Pull Requests", collection["totalPullRequestContributions"]),
    ("Issues", collection["totalIssueContributions"]),
    ("Repos contributed to", collection["totalRepositoryContributions"]),
]

fig, ax = plt.subplots(figsize=(9, 2.2), dpi=150)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.axis("off")

n = len(stats)
for i, (label, value) in enumerate(stats):
    cx = (i + 0.5) / n
    ax.text(cx, 0.62, str(value), transform=ax.transAxes, ha="center", va="center",
            fontsize=26, fontweight="bold", color=LINE)
    ax.text(cx, 0.22, label, transform=ax.transAxes, ha="center", va="center",
            fontsize=10, color=TEXT)
    if i > 0:
        ax.axvline(i / n, color=GRID, linewidth=1, ymin=0.1, ymax=0.9)

fig.suptitle(f"{USERNAME}'s Activity (past year)", color=TEXT, fontsize=12, fontweight="bold", y=0.98)
plt.tight_layout()
plt.savefig("assets/stats.svg", format="svg")
plt.close(fig)
print("Saved assets/stats.svg")


# ---------- 3. Top languages bar chart ----------

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
    lang_url = repo["languages_url"]
    lang_resp = requests.get(lang_url, headers=HEADERS_REST, timeout=30)
    if lang_resp.ok:
        for lang, byte_count in lang_resp.json().items():
            lang_totals[lang] += byte_count

top_langs = sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
total_bytes = sum(v for _, v in top_langs) or 1
lang_names = [k for k, _ in top_langs]
lang_pcts = [100 * v / total_bytes for _, v in top_langs]

fig, ax = plt.subplots(figsize=(9, 3), dpi=150)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

y_pos = range(len(lang_names))
bars = ax.barh(list(y_pos), lang_pcts, color=[PALETTE[i % len(PALETTE)] for i in y_pos])
ax.set_yticks(list(y_pos))
ax.set_yticklabels(lang_names, color=TEXT, fontsize=10)
ax.invert_yaxis()

for bar, pct in zip(bars, lang_pcts):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
            f"{pct:.1f}%", va="center", fontsize=9, color=TEXT)

for spine in ["top", "right", "bottom", "left"]:
    ax.spines[spine].set_visible(False)
ax.set_xticks([])
ax.set_title(f"{USERNAME}'s Most Used Languages", color=TEXT, fontsize=12,
             fontweight="bold", pad=12)

plt.tight_layout()
plt.savefig("assets/languages.svg", format="svg")
plt.close(fig)
print("Saved assets/languages.svg")