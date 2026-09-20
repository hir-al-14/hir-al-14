import os
import json
import urllib.request
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from html import escape
import math

USERNAME = "hir-al-14"
TOKEN = os.environ["GITHUB_TOKEN"]

# -------------------------------------------------------
# GitHub GraphQL helper
# -------------------------------------------------------

def graphql(query, variables=None):
    body = json.dumps({
        "query": query,
        "variables": variables or {}
    }).encode()

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USERNAME,
        },
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    return result["data"]


# -------------------------------------------------------
# Basic account information
# -------------------------------------------------------

profile_query = """
query($login: String!) {
  user(login: $login) {
    createdAt

    repositories(
      first: 1
      privacy: PUBLIC
      ownerAffiliations: OWNER
    ) {
      totalCount
    }

    repositoriesContributedTo(
      first: 1
      contributionTypes: [
        COMMIT
        ISSUE
        PULL_REQUEST
        PULL_REQUEST_REVIEW
      ]
    ) {
      totalCount
    }
  }
}
"""

profile = graphql(profile_query, {"login": USERNAME})["user"]

public_repos = profile["repositories"]["totalCount"]
contributed_to = profile["repositoriesContributedTo"]["totalCount"]

created_at = datetime.fromisoformat(
    profile["createdAt"].replace("Z", "+00:00")
)


# -------------------------------------------------------
# ALL-TIME PR + issue counts
#
# GitHub limits a single ContributionsCollection time span,
# so query each contribution year and add the totals.
# -------------------------------------------------------

years_query = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionYears
    }
  }
}
"""

years = graphql(years_query, {"login": USERNAME})[
    "user"
]["contributionsCollection"]["contributionYears"]


year_query = """
query(
  $login: String!,
  $from: DateTime!,
  $to: DateTime!
) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""

total_prs = 0
total_issues = 0

now = datetime.now(timezone.utc)

for year in years:

    start = datetime(year, 1, 1, tzinfo=timezone.utc)

    if year == now.year:
        end = now
    else:
        end = datetime(
            year,
            12,
            31,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )

    result = graphql(
        year_query,
        {
            "login": USERNAME,
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
    )

    collection = result["user"]["contributionsCollection"]

    total_prs += collection["totalPullRequestContributions"]
    total_issues += collection["totalIssueContributions"]


# -------------------------------------------------------
# Last 12 months
# -------------------------------------------------------

today = datetime.now(timezone.utc)

# Start on the first day of the month 11 months ago.
year = today.year
month = today.month - 11

while month <= 0:
    month += 12
    year -= 1

start_date = datetime(
    year,
    month,
    1,
    tzinfo=timezone.utc
)

calendar_query = """
query(
  $login: String!,
  $from: DateTime!,
  $to: DateTime!
) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions

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

result = graphql(
    calendar_query,
    {
        "login": USERNAME,
        "from": start_date.isoformat(),
        "to": today.isoformat(),
    },
)

calendar = result[
    "user"
]["contributionsCollection"]["contributionCalendar"]

total_contributions = calendar["totalContributions"]


# -------------------------------------------------------
# Turn daily contributions into monthly totals
# -------------------------------------------------------

monthly = defaultdict(int)

for week in calendar["weeks"]:
    for day in week["contributionDays"]:

        date = datetime.strptime(
            day["date"],
            "%Y-%m-%d"
        )

        key = (date.year, date.month)

        monthly[key] += day["contributionCount"]


months = []

y = start_date.year
m = start_date.month

for _ in range(12):

    months.append({
        "year": y,
        "month": m,
        "label": datetime(y, m, 1).strftime("%b"),
        "value": monthly[(y, m)],
    })

    m += 1

    if m == 13:
        m = 1
        y += 1


# -------------------------------------------------------
# Account age
# -------------------------------------------------------

age_days = (today - created_at).days
age_years = age_days // 365

if age_years == 0:
    joined_text = "Joined GitHub this year"
elif age_years == 1:
    joined_text = "Joined GitHub 1 year ago"
else:
    joined_text = f"Joined GitHub {age_years} years ago"


# -------------------------------------------------------
# Graph coordinates
# -------------------------------------------------------

GRAPH_X = 365
GRAPH_Y = 88
GRAPH_WIDTH = 390
GRAPH_HEIGHT = 90

values = [month["value"] for month in months]

maximum = max(values) if max(values) > 0 else 1

points = []

for index, value in enumerate(values):

    x = GRAPH_X + (
        index * GRAPH_WIDTH / (len(values) - 1)
    )

    y = (
        GRAPH_Y
        + GRAPH_HEIGHT
        - math.sqrt(value / maximum) * GRAPH_HEIGHT
    )

    points.append((x, y))


line_points = " ".join(
    f"{x:.1f},{y:.1f}"
    for x, y in points
)

area_points = (
    f"{GRAPH_X},{GRAPH_Y + GRAPH_HEIGHT} "
    + line_points
    + f" {GRAPH_X + GRAPH_WIDTH},{GRAPH_Y + GRAPH_HEIGHT}"
)


# -------------------------------------------------------
# Month labels
# -------------------------------------------------------

month_labels = ""

for index, month_data in enumerate(months):

    x = GRAPH_X + (
        index * GRAPH_WIDTH / (len(months) - 1)
    )

    # Label every other month so the graph stays clean.
    if index % 2 == 0 or index == len(months) - 1:

        month_labels += f"""
        <text
          x="{x:.1f}"
          y="200"
          text-anchor="middle"
          class="month"
        >
          {escape(month_data["label"])}
        </text>
        """


# -------------------------------------------------------
# Graph dots
# -------------------------------------------------------

dots = ""

for x, y in points:

    dots += f"""
    <circle
      cx="{x:.1f}"
      cy="{y:.1f}"
      r="3.5"
      class="dot"
    />
    """


# -------------------------------------------------------
# SVG
# -------------------------------------------------------

svg = f"""
<svg
  width="800"
  height="270"
  viewBox="0 0 800 270"
  xmlns="http://www.w3.org/2000/svg"
  role="img"
  aria-labelledby="title desc"
>

<title id="title">GitHub Stats for {USERNAME}</title>

<desc id="desc">
GitHub activity statistics and monthly contribution graph.
</desc>

<style>

  .card {{
    fill: #111923;
    stroke: #263747;
    stroke-width: 1;
  }}

  .title {{
    fill: #F1F7FF;
    font-size: 20px;
    font-weight: 600;
  }}

  .number {{
    fill: #F1F7FF;
    font-size: 15px;
    font-weight: 600;
  }}

  .label {{
    fill: #AFC5D8;
    font-size: 15px;
  }}

  .icon {{
    fill: #C7E5FF;
    font-size: 15px;
    font-weight: 600;
  }}

  .small {{
    fill: #AFC5D8;
    font-size: 12px;
  }}

  .month {{
    fill: #8299AA;
    font-size: 10px;
  }}

  .grid {{
    stroke: #20303F;
    stroke-width: 1;
  }}

  .area {{
    fill: #162B3D;
  }}

  .graph {{
    fill: none;
    stroke: #82CFFF;
    stroke-width: 3;
    stroke-linecap: round;
    stroke-linejoin: round;
  }}

  .dot {{
    fill: #D9EFFF;
    stroke: #82CFFF;
    stroke-width: 1;
  }}

  text {{
    font-family:
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      Helvetica,
      Arial,
      sans-serif;
  }}

</style>


<!-- BACKGROUND -->

<rect
  class="card"
  x="1"
  y="1"
  width="798"
  height="268"
  rx="14"
/>


<!-- TITLE -->

<text
  x="30"
  y="40"
  class="title"
>
  hiral's github stats
</text>


<!-- LEFT STATS -->

<text x="31" y="79" class="icon">●</text>

<text x="58" y="79" class="number">
  {total_contributions:,}
</text>

<text x="112" y="79" class="label">
  Contributions
</text>


<text x="31" y="110" class="icon">▣</text>

<text x="58" y="110" class="number">
  {public_repos:,}
</text>

<text x="112" y="110" class="label">
  Public Repos
</text>


<text x="31" y="141" class="icon">⑂</text>

<text x="58" y="141" class="number">
  {total_prs:,}
</text>

<text x="112" y="141" class="label">
  Total PRs
</text>


<text x="33" y="172" class="icon">!</text>

<text x="58" y="172" class="number">
  {total_issues:,}
</text>

<text x="112" y="172" class="label">
  Total Issues
</text>


<text x="31" y="203" class="icon">▤</text>

<text x="58" y="203" class="number">
  {contributed_to:,}
</text>

<text x="112" y="203" class="label">
  Contributed To
</text>


<text x="31" y="234" class="icon">◷</text>

<text x="58" y="234" class="label">
  {escape(joined_text)}
</text>


<!-- GRAPH GRID -->

<line
  x1="{GRAPH_X}"
  y1="{GRAPH_Y}"
  x2="{GRAPH_X + GRAPH_WIDTH}"
  y2="{GRAPH_Y}"
  class="grid"
/>

<line
  x1="{GRAPH_X}"
  y1="{GRAPH_Y + GRAPH_HEIGHT / 2}"
  x2="{GRAPH_X + GRAPH_WIDTH}"
  y2="{GRAPH_Y + GRAPH_HEIGHT / 2}"
  class="grid"
/>

<line
  x1="{GRAPH_X}"
  y1="{GRAPH_Y + GRAPH_HEIGHT}"
  x2="{GRAPH_X + GRAPH_WIDTH}"
  y2="{GRAPH_Y + GRAPH_HEIGHT}"
  class="grid"
/>


<!-- GRAPH AREA -->

<polygon
  points="{area_points}"
  class="area"
/>


<!-- GRAPH LINE -->

<polyline
  points="{line_points}"
  class="graph"
/>


<!-- GRAPH DOTS -->

{dots}


<!-- MONTHS -->

{month_labels}


<!-- GRAPH CAPTION -->

<text
  x="{GRAPH_X + GRAPH_WIDTH / 2}"
  y="230"
  text-anchor="middle"
  class="small"
>
  monthly contributions · last 12 months
</text>

</svg>
"""


# -------------------------------------------------------
# Save
# -------------------------------------------------------

Path("assets").mkdir(exist_ok=True)

Path("assets/github-stats.svg").write_text(
    svg,
    encoding="utf-8"
)

print("Generated assets/github-stats.svg")
print(f"Contributions: {total_contributions}")
print(f"Public repos: {public_repos}")
print(f"PRs: {total_prs}")
print(f"Issues: {total_issues}")
print(f"Contributed to: {contributed_to}")
