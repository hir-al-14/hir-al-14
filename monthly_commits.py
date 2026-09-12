import os
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("GH_USERNAME", "hir-al-14")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
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
    headers={"Authorization": f"Bearer {TOKEN}"},
    timeout=30,
)
resp.raise_for_status()
weeks = resp.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

monthly = defaultdict(int)
for week in weeks:
    for day in week["contributionDays"]:
        date = datetime.strptime(day["date"], "%Y-%m-%d")
        monthly[date.strftime("%Y-%m")] += day["contributionCount"]

months = sorted(monthly.keys())
counts = [monthly[m] for m in months]
labels = [datetime.strptime(m, "%Y-%m").strftime("%b") for m in months]

BG = "#F7F0FB"
LINE = "#7B2CBF"
MARK = "#9D4EDD"
TEXT = "#4A3F55"
GRID = "#E4D4F4"

fig, ax = plt.subplots(figsize=(9, 3), dpi=150)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

ax.plot(labels, counts, color=LINE, linewidth=2.5, marker="o", markersize=5,
        markerfacecolor=MARK, markeredgecolor=MARK, zorder=3)
ax.fill_between(range(len(labels)), counts, color=MARK, alpha=0.15, zorder=1)

for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color("#C9A9E0")
ax.tick_params(colors=TEXT, labelsize=9)
ax.set_title(f"{USERNAME}'s Monthly Contributions", color=TEXT, fontsize=12,
             fontweight="bold", pad=12)
ax.grid(axis="y", color=GRID, linewidth=0.7, zorder=0)

plt.tight_layout()
os.makedirs("assets", exist_ok=True)
plt.savefig("assets/monthly-commits.svg", format="svg")
print("Saved assets/monthly-commits.svg")