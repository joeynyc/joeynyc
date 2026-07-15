#!/usr/bin/env python3
"""Render the GitHub contribution calendar as a honeycomb hex grid SVG.

Zero dependencies (stdlib only). Reads GITHUB_TOKEN from the environment
(falls back to `gh auth token` for local runs) and writes contrib.svg.
"""
import datetime
import json
import os
import subprocess
import sys
import urllib.request

LOGIN = "joeynyc"
OUT = sys.argv[1] if len(sys.argv) > 1 else "contrib.svg"

# palette — mirrors Honeycomb's LabTheme phosphor scale
BG = "#0A0E0A"
BORDER = "#334D33"
STROKE = "#1F2E1F"
MUTED = "#597A59"
PHOSPHOR = "#7DFF3B"
LEVEL_FILL = ["#101B10", "#26471C", "#3F7A26", "#5CBF2E", "#7DFF3B"]
LEVEL_NAME = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
              "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}
"""


def fetch_calendar():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True,
                               text=True, check=True).stdout.strip()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def hex_points(r):
    return f"0,{-r:.2f} {r*0.866:.2f},{-r/2:.2f} {r*0.866:.2f},{r/2:.2f} 0,{r:.2f} {-r*0.866:.2f},{r/2:.2f} {-r*0.866:.2f},{-r/2:.2f}"


def main():
    cal = fetch_calendar()
    weeks = cal["weeks"]
    total = cal["totalContributions"]
    today = datetime.date.today().isoformat()

    # layout: pointy-top hexes, one column per week, odd day-rows offset right
    R = 7.0          # layout radius
    COL = R * 1.732  # 12.12 horizontal spacing
    ROW = R * 1.5    # 10.5 vertical spacing
    X0, Y0 = 26.0, 74.0
    n_weeks = len(weeks)

    cells = []
    pulse_i = 0
    for w, week in enumerate(weeks):
        for day in week["contributionDays"]:
            d = day["weekday"]
            lvl = LEVEL_NAME[day["contributionLevel"]]
            x = X0 + w * COL + (COL / 2 if d % 2 else 0)
            y = Y0 + d * ROW
            cls, style = "", ""
            if lvl == 4:
                cls = ' class="p"'
                style = f' style="animation-delay:-{(pulse_i % 8) * 0.45:.2f}s"'
                pulse_i += 1
            extra = ""
            if day["date"] == today:
                extra = f' stroke="{PHOSPHOR}" stroke-width="1.5"'
            cells.append(
                f'<use href="#h" x="{x:.1f}" y="{y:.1f}" fill="{LEVEL_FILL[lvl]}"{extra}{cls}{style}>'
                f'<title>{day["date"]}: {day["contributionCount"]} contributions</title></use>'
            )

    width = 880
    height = 190
    grid_right = X0 + (n_weeks - 1) * COL + COL / 2

    legend = []
    lx = width - 80
    for lvl in range(4, -1, -1):
        legend.append(f'<use href="#h" x="{lx:.1f}" y="160" fill="{LEVEL_FILL[lvl]}"/>')
        lx -= 15
    legend_g = "".join(legend)

    updated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" font-family="SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace" role="img" aria-labelledby="cgTitle">
  <title id="cgTitle">{total} contributions in the last year, rendered as a honeycomb hex grid</title>
  <defs>
    <clipPath id="panelClip"><rect x="2" y="2" width="{width - 4}" height="{height - 4}" rx="12"/></clipPath>
    <pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse">
      <rect width="4" height="1" fill="#000000" opacity="0.28"/>
    </pattern>
    <polygon id="h" points="{hex_points(6.3)}"/>
  </defs>
  <style>
    .p {{ animation: pulse 3.6s ease-in-out infinite; }}
    @keyframes pulse {{ 0%, 100% {{ fill-opacity: 1; }} 50% {{ fill-opacity: 0.35; }} }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
  <rect x="2" y="2" width="{width - 4}" height="{height - 4}" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
  <text x="26" y="34" fill="{MUTED}" font-size="13">joey@nyc :: hive activity — last 52 weeks</text>
  <text x="{width - 26}" y="34" text-anchor="end" fill="{PHOSPHOR}" font-size="14" font-weight="bold">{total:,} CONTRIBUTIONS</text>
  <line x1="2" y1="48" x2="{width - 2}" y2="48" stroke="{STROKE}" stroke-width="1.5"/>
  <g stroke="{STROKE}" stroke-width="1">
    {"".join(cells)}
  </g>
  <text x="26" y="164" fill="{MUTED}" font-size="11"># regenerated nightly · {updated}</text>
  <text x="{width - 152}" y="164" text-anchor="end" fill="{MUTED}" font-size="11">LESS</text>
  <g stroke="{STROKE}" stroke-width="1">{legend_g}</g>
  <text x="{width - 26}" y="164" text-anchor="end" fill="{MUTED}" font-size="11">MORE</text>
  <g clip-path="url(#panelClip)" pointer-events="none">
    <rect x="2" y="2" width="{width - 4}" height="{height - 4}" fill="url(#scan)"/>
  </g>
</svg>
"""
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT}: {n_weeks} weeks, {total} contributions")


if __name__ == "__main__":
    main()
