#!/usr/bin/env python3

import json
import math
import os
import sys
import urllib.request

USERNAME = os.environ.get("GITHUB_USERNAME", "")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")
OUTPUT   = "dist/github-contribution-grid-snake-avoid-dark.svg"

# Layout constants
CELL = 11
GAP  = 2
PX   = 16   # horizontal padding
PY   = 28   # vertical padding
ROWS = 7

# Colors (purple snake, standard GitHub contribution greens on dark bg)
SNAKE_BODY  = "#A78BFA"
SNAKE_HEAD  = "#7C3AED"
CONTRIB_COLS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

SNAKE_CELLS  = 5          # visual length of snake in cells
FRAME_MS     = 120        # ms per cell step


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def contrib_color(n: int) -> str:
    if n == 0:  return CONTRIB_COLS[0]
    if n <= 2:  return CONTRIB_COLS[1]
    if n <= 5:  return CONTRIB_COLS[2]
    if n <= 10: return CONTRIB_COLS[3]
    return CONTRIB_COLS[4]


def cell_cx(c: int) -> float:
    return PX + c * (CELL + GAP) + CELL / 2


def cell_cy(r: int) -> float:
    return PY + r * (CELL + GAP) + CELL / 2


def rect_x(c: int) -> int:
    return PX + c * (CELL + GAP)


def rect_y(r: int) -> int:
    return PY + r * (CELL + GAP)


# ──────────────────────────────────────────────────────────────────────────────
# GitHub API
# ──────────────────────────────────────────────────────────────────────────────

def fetch_contributions() -> list[list[int]]:
    """Returns grid[col][weekday] = contribution count."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays { contributionCount weekday }
            }
          }
        }
      }
    }"""
    body = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "custom-snake-action",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    weeks = (
        data["data"]["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["weeks"]
    )
    grid = []
    for week in weeks:
        col = [0] * ROWS
        for day in week["contributionDays"]:
            col[day["weekday"]] = day["contributionCount"]
        grid.append(col)
    return grid


# ──────────────────────────────────────────────────────────────────────────────
# Path builder  — serpentine through EMPTY cells only
# ──────────────────────────────────────────────────────────────────────────────

def build_path(grid: list[list[int]]) -> list[tuple[int, int]]:
    cols = len(grid)
    path = []
    for c in range(cols):
        row_range = range(ROWS) if c % 2 == 0 else range(ROWS - 1, -1, -1)
        for r in row_range:
            if grid[c][r] == 0:
                path.append((c, r))
    return path


# ──────────────────────────────────────────────────────────────────────────────
# SVG generator
# ──────────────────────────────────────────────────────────────────────────────

def generate_svg(grid: list[list[int]], path: list[tuple[int, int]]) -> str:
    cols = len(grid)
    W = PX * 2 + cols * (CELL + GAP)
    H = PY * 2 + ROWS * (CELL + GAP)

    if len(path) < 2:
        # Fallback: whole grid in serpentine order
        path = [
            (c, r)
            for c in range(cols)
            for r in (range(ROWS) if c % 2 == 0 else range(ROWS - 1, -1, -1))
        ]

    # Waypoints (centres of each cell in path)
    pts = [(cell_cx(c), cell_cy(r)) for c, r in path]

    # Build SVG path string
    d = "M {:.1f} {:.1f} ".format(*pts[0]) + " ".join(
        "L {:.1f} {:.1f}".format(x, y) for x, y in pts[1:]
    )

    # Compute total path length (approximation: sum of segment lengths)
    seg_lengths = [
        math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    ]
    path_len = sum(seg_lengths)

    # Snake body length in SVG units
    snake_px = (CELL + GAP) * SNAKE_CELLS

    # Animation duration
    total_cells = len(path)
    dur_s = max(6, round(total_cells * FRAME_MS / 1000, 1))

    # dashoffset goes from (path_len + snake_px) → -(snake_px)
    # so the snake enters from start, travels full length, exits at end
    dash_from = path_len + snake_px
    dash_to   = -snake_px

    out: list[str] = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">')
    out.append(f'  <rect width="{W}" height="{H}" fill="#0D0B1A"/>')

    # ── Static contribution cells (always fully visible) ──────────────────────
    for c in range(cols):
        for r in range(ROWS):
            count = grid[c][r] if c < len(grid) else 0
            out.append(
                f'  <rect x="{rect_x(c)}" y="{rect_y(r)}" '
                f'width="{CELL}" height="{CELL}" rx="2" fill="{contrib_color(count)}"/>'
            )

    # ── Snake path definition ─────────────────────────────────────────────────
    out.append("  <defs>")
    out.append(f'    <path id="snakePath" d="{d}"/>')
    out.append("  </defs>")

    # ── Snake body (animated stroke along the path) ───────────────────────────
    anim = (
        f'<animate attributeName="stroke-dashoffset" '
        f'from="{dash_from:.1f}" to="{dash_to:.1f}" '
        f'dur="{dur_s}s" repeatCount="indefinite" calcMode="linear"/>'
    )

    # Body
    out.append(
        f'  <use href="#snakePath" fill="none" '
        f'stroke="{SNAKE_BODY}" stroke-width="{CELL - 1}" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-dasharray="{snake_px:.1f} {path_len:.1f}" '
        f'opacity="0.9">'
    )
    out.append(f"    {anim}")
    out.append("  </use>")

    # Head (brighter, 1px larger)
    out.append(
        f'  <use href="#snakePath" fill="none" '
        f'stroke="{SNAKE_HEAD}" stroke-width="{CELL + 1}" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-dasharray="1 {path_len:.1f}" '
        f'opacity="1">'
    )
    out.append(f"    {anim}")
    out.append("  </use>")

    out.append("</svg>")
    return "\n".join(out)



def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    try:
        grid = fetch_contributions()
        print(f"Fetched {len(grid)} weeks of contributions.")
    except Exception as exc:
        print(f"[WARNING] Could not fetch contributions: {exc}", file=sys.stderr)
        print("Using blank grid as fallback.")
        grid = [[0] * ROWS for _ in range(52)]

    path = build_path(grid)
    print(f"Snake path: {len(path)} empty cells to travel through.")

    svg = generate_svg(grid, path)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Generated: {OUTPUT}")


if __name__ == "__main__":
    main()
