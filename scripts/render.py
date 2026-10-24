#!/usr/bin/env python3
"""Render the profile README and themed SVG assets into dist/.

Adapted from ../zeroherolin/scripts/render.py: same 840px canvas, typography,
project shelf, section rules, language chart and four-column fork tile layout.
Only Python's standard library is required. GITHUB_TOKEN is optional locally.
The asset manifest includes the separately generated contribution snakes.
"""

import json
import math
import os
import re
import unicodedata
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USER = "LinZzzzJ"
NAME = "LinZzzzJ"
MOTTO = "Think Deep. Automate the Rest."
ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "assets" / "icons" / "mono"
BUILD = ROOT / "dist"
README = ROOT / "README.md"
IMAGES = f"https://raw.githubusercontent.com/{USER}/{USER}/output/assets/"
SNAKES = ["snake.svg", "snake-dark.svg"]
TZ = timezone(timedelta(hours=8))

WIDTH = 840  # canvas of full-width images, about the width of a profile README
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"

# Projects in shelf order: (public repository, area, description).
PROJECTS = [
    ("FitTrack", "App",
     "Local-first fitness logs with AI assistance and trend analysis."),
]

# Each category is a column; four categories form a block. Learning and
# Uncategorized instead fill all columns row by row, matching the reference.
FORKS = [
    ("AI AGENTS", ["dsh-purge"]),
    ("VIBECODING APP", ["openGym_FitTrack"]),
]
ROW_MAJOR = ("Learning", "Uncategorized")

# Compact hardware-focused skills; application dependencies stay with the project.
STACK = [
    ("Languages", [("MATLAB", "#e16737"), ("Python", "#3572A5"),
                   ("TypeScript", "#3178c6"), ("JavaScript", "#f1e05a"),
                   ("HTML", "#e34c26"), ("CSS", "#663399")]),
    ("Tools & data", [("SQLite", "database"), ("Git", "git"), ("Node.js", "nodejs")]),
    ("Hardware", [("ARM", "chip"), ("FPGA", "fpga"), ("Linux", "linux"),
                  ("Hardware", "circuit")]),
    ("Signal & power", [("SI Simulation", "signal"), ("PI Simulation", "power"),
                        ("High-Speed Signals", "signal"), ("Signal integrity", "signal"),
                        ("Power design", "power")]),
    ("Interfaces", [("PCIe", "bus"), ("USB", "bus"), ("MIPI", "bus")]),
]

THEMES = {
    "light": {"fg": "#1f2328", "muted": "#59636e", "faint": "#8c959f", "line": "#d1d9e0",
              "page": "#ffffff", "card": ("#ffffff", 1)},
    "dark": {"fg": "#f0f6fc", "muted": "#9198a1", "faint": "#656c76", "line": "#3d444d",
             "page": "#0d1117", "card": ("#000000", .36)},
}

# github-linguist colors; anything missing falls back to gray.
COLORS = {
    "Assembly": "#6E4C13", "C": "#555555", "C#": "#7355dd", "C++": "#f34b7d",
    "CMake": "#DA3434", "CSS": "#663399", "Cuda": "#3A4E3A",
    "Dockerfile": "#384d54", "GDScript": "#355570", "Go": "#00ADD8",
    "HTML": "#e34c26", "Java": "#b07219", "JavaScript": "#f1e05a",
    "Jupyter Notebook": "#DA5B0B", "LLVM": "#185619", "Lua": "#000080",
    "MATLAB": "#e16737", "MLIR": "#5EC8DB", "Makefile": "#427819",
    "OpenCL": "#ed2e2d", "Python": "#3572A5", "Rust": "#dea584",
    "Shell": "#89e051", "Svelte": "#ff3e00", "SystemVerilog": "#DAE1C2",
    "Tcl": "#e4cc98", "TeX": "#3D6117", "TypeScript": "#3178c6",
    "VHDL": "#adb2cb", "Verilog": "#b2b7f8", "Vue": "#41b883",
}
OTHER = "#8c959f"
TOP_LANGUAGES = 7

# Helvetica advance widths (1/1000 em) for printable ASCII, to wrap sans text;
# full-width characters use one em. Platform fonts differ a little, so
# wrapping keeps SLACK in reserve. Monospace text is taken as 0.6 em per glyph.
_ADVANCE = dict(zip(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
    [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
     556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
     1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
     667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
     333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
     556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]))
SLACK = 1.1


def sans_width(text, size):
    return sum(1000 if unicodedata.east_asian_width(c) in ("W", "F")
               else _ADVANCE.get(c, 556) for c in text) * size / 1000


def mono_width(text, size, spacing=0):
    return sum((size if unicodedata.east_asian_width(c) in ("W", "F")
                else 0.6 * size) + spacing for c in text)


def wrap(content, size, width, max_lines):
    # Split CJK characters separately: unlike English, they need no spaces.
    tokens = re.findall(r"[^\s\u2e80-\ua4cf\uac00-\ud7af\uf900-\ufaff]+|[^\x00-\x7f]|\s+", content)
    lines, line = [], ""
    for token in tokens:
        candidate = line + token
        if line and sans_width(candidate.rstrip(), size) * SLACK > width:
            lines.append(line.rstrip())
            line = token.lstrip()
        else:
            line = candidate
    if line.strip():
        lines.append(line.rstrip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and sans_width(lines[-1] + "…", size) * SLACK > width:
            lines[-1] = lines[-1][:-1].rstrip()
        lines[-1] += "…"
    return lines


def fit(text, size, width, min_size):
    """Shrink a monospace label down to min_size to fit width, then cut it short."""
    while size > min_size and mono_width(text, size) > width:
        size -= 0.5
    while mono_width(text, size) > width:
        text = text[:-2] + "…"
    return text, size


# -- SVG building blocks -------------------------------------------------------

def svg(width, height, title, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title, {chr(34): "&quot;"})}">\n'
            f'<title>{escape(title)}</title>\n'
            f'<defs><style>.m{{font-family:{MONO}}}.s{{font-family:{SANS}}}</style>{defs}</defs>\n'
            f'{body}\n</svg>\n')


def text(x, y, content, size, fill, cls="m", anchor=None, weight=None, spacing=None):
    attrs = f'class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    if weight:
        attrs += f' font-weight="{weight}"'
    if spacing:
        attrs += f' letter-spacing="{spacing}"'
    return f"<text {attrs}>{escape(content)}</text>"


def icon(name, x, y, size, fill):
    """Inline assets/icons/<name>.svg (a square, single-color icon) at size px."""
    source = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    box = float(re.search(r'viewBox="0 0 ([\d.]+) [\d.]+"', source).group(1))
    paths = "".join(re.findall(r'<path\b[^>]*?/>', source))
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({size / box:.4f})" '
            f'fill="{fill}" color="{fill}">{paths}</g>')


def swatch(x, y, size, color, t):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" rx="{size / 5:g}" '
            f'fill="{color}" stroke="{t["fg"]}" stroke-opacity=".12"/>')


def rule(x0, x1, y, t):
    return f'<path d="M {x0:.1f} {y} H {x1:.1f}" stroke="{t["line"]}"/>'


# -- header --------------------------------------------------------------------

def render_name(t):
    return svg(WIDTH, 58, NAME, text(-2, 46, NAME, 44, t["fg"], cls="s", weight="700", spacing=-1))


def render_stack(t):
    row_h, label_w, gap = 32, 112, 24
    body = [rule(0, WIDTH, 0.5, t)]
    for r, (label, items) in enumerate(STACK):
        base = 21 + r * row_h
        body.append(text(0, base, label.upper(), 10, t["faint"], weight="700", spacing=1.5))
        x = label_w
        for name, glyph in items:
            if glyph.startswith("#"):
                body.append(swatch(x, base - 9, 9, glyph, t))
            else:
                body.append(icon(glyph, x - 1, base - 10.5, 12, t["muted"]))
            body.append(text(x + 17, base, name, 12, t["fg"]))
            x += 17 + mono_width(name, 12) + gap
        if x - gap > WIDTH:
            raise ValueError(f"stack row {label!r} is {x - gap:.0f}px wide, over {WIDTH}")
        body.append(rule(0, WIDTH, (r + 1) * row_h + 0.5, t))
    return svg(WIDTH, len(STACK) * row_h + 1, "Languages and tooling", "\n".join(body))


# -- section titles ------------------------------------------------------------

def render_section(title, count, hint, t, hint_icon=None):
    height, base = 56, 40
    caps = title.upper()
    x = mono_width(caps, 13, 2.5)
    body = [text(0, base, caps, 13, t["fg"], weight="700", spacing=2.5)]
    if count is not None:
        body.append(text(x + 8, base, str(count), 12, t["muted"]))
        x += 8 + mono_width(str(count), 12)
    end = WIDTH
    if hint:
        body.append(text(WIDTH, base, hint, 10.5, t["muted"], anchor="end", spacing=1))
        end -= mono_width(hint, 10.5, 1)
        if hint_icon:
            end -= 15
            body.append(icon(hint_icon, end, base - 9, 10, t["muted"]))
        end -= 14
    body.append(rule(x + 14, end, base - 4.5, t))
    return svg(WIDTH, height, title, "\n".join(body))


# -- project cards -------------------------------------------------------------

CARD_W, CARD_H, CARD_GAP = 236, 141, 12
SHELF_ROWS = min(2, len(PROJECTS))  # retain shelf order without an empty second row


def render_project(name, area, desc, repo, gap_below, t):
    """Name and description; under a rule, language, stars and forks as on
    GitHub's pinned repositories, with the area aligned to the right."""
    lang = repo.get("language")
    color = COLORS.get(lang, OTHER) if lang else OTHER
    x1, y1 = CARD_W - 0.5, CARD_H - 0.5
    left, right = 18, CARD_W - 18
    # A faint wash of the language color fades out halfway down the card.
    defs = (f'<linearGradient id="wash" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".1"/>'
            f'<stop offset=".55" stop-color="{color}" stop-opacity="0"/></linearGradient>')
    frame = f'x="0.5" y="0.5" width="{x1 - 0.5}" height="{y1 - 0.5}" rx="8"'
    fill, opacity = t["card"]  # a veil, so dark cards sit a shade below the tray in every dark theme
    body = [f'<rect {frame} fill="{fill}" fill-opacity="{opacity}"/>',
            f'<rect {frame} fill="url(#wash)" stroke="{t["line"]}"/>']
    label, size = fit(name, 15, right - left, 11)
    body.append(text(left, 32, label, size, t["fg"], weight="600"))
    for i, line in enumerate(wrap(desc, 12, right - left, 3)):
        body.append(text(left, 54 + i * 17, line, 12, t["muted"], cls="s"))
    body.append(rule(left, right, 102.5, t))

    base, x, gap = 122, left, 10
    if lang:
        body.append(swatch(x, base - 8, 8, color, t))
        body.append(text(x + 14, base, lang, 11, t["muted"]))
        x += 14 + mono_width(lang, 11) + gap
    for key, glyph in (("stargazers_count", "star"), ("forks_count", "repo-forked")):
        count = repo.get(key, 0)
        if count:
            body.append(icon(glyph, x, base - 10, 12, t["faint"]))
            body.append(text(x + 16, base, str(count), 11, t["muted"]))
            x += 16 + mono_width(str(count), 11) + gap
    caps = area.upper()
    if x - gap + 12 > right - mono_width(caps, 10, 1.2):
        warn(f"{name}: language, stars and forks run into the area label")
    body.append(text(right, base, caps, 10, t["muted"], anchor="end", spacing=1.2))
    height = CARD_H + (CARD_GAP if gap_below else 0)
    return svg(CARD_W + CARD_GAP, height, f"{name}: {desc}", "\n".join(body), defs)


# -- fork cards ------------------------------------------------------------------

COLUMNS = 4                            # fork columns per block of the grid
TILE_W, TILE_H = WIDTH // COLUMNS, 36  # includes a 12px gap on the right
HEADING_H = (26, 40)                   # heading rows: first block, later blocks (spaced apart)


def compact(n):
    """1234 -> 1.2k, the way GitHub abbreviates counts."""
    if n < 1000:
        return str(n)
    return f"{n / 1000:.1f}k" if n < 9950 else f"{round(n / 1000)}k"


def render_fork(name, behind, t):
    """Fork card; on the right a check if the default branch is level with
    upstream, the number of commits it is behind, or an x if that is unknown."""
    x1 = TILE_W - 12.5
    right = x1 - 9
    body = [f'<rect x="0.5" y="5.5" width="{x1 - 0.5}" height="25" rx="4" fill="none" stroke="{t["faint"]}"/>']
    if behind == 0:
        status_w, title = 12, f"{name}: up to date with upstream"
        body.append(icon("check", right - 12, 12, 12, t["muted"]))
    elif behind:
        label = compact(behind)
        status_w, title = mono_width(label, 11) + 12, f"{name}: {behind} commits behind upstream"
        body.append(icon("arrow-down", right - status_w, 13, 10, t["faint"]))
        body.append(text(right, 22.5, label, 11, t["muted"], anchor="end"))
    else:
        status_w, title = 12, f"{name}: sync status unavailable"
        body.append(icon("x", right - 12, 12, 12, t["muted"]))
    name_label, size = fit(name, 12, right - status_w - 10 - 12, 12)
    body.append(text(12, 22.5, name_label, size, t["fg"]))
    return svg(TILE_W, TILE_H, title, "\n".join(body))


def render_fork_heading(title, count, height, t):
    right, base = TILE_W - 12, height - 15
    body = [text(0, base, title.upper(), 11, t["fg"], weight="700", spacing=1),
            text(right, base, str(count), 11, t["faint"], anchor="end"),
            rule(0, right, base + 8.5, t)]
    return svg(TILE_W, height, title, "\n".join(body))


# -- languages -----------------------------------------------------------------

def render_languages(shares, t):
    if not shares:
        return svg(WIDTH, 46, "Languages",
                   text(0, 30, "No public language data yet.", 12, t["muted"]))
    cols, gap = 4, 3
    rows = math.ceil(len(shares) / cols)
    col_w = WIDTH / cols
    height = 40 + (rows - 1) * 24 + 6
    body, x = [], 0.0
    usable = WIDTH - gap * (len(shares) - 1)
    for lang, share in shares:
        w = share * usable
        body.append(f'<rect x="{x:.2f}" y="4" width="{w:.2f}" height="10" rx="2" '
                    f'fill="{COLORS.get(lang, OTHER)}"/>')
        x += w + gap
    for i, (lang, share) in enumerate(shares):
        cx, y = (i % cols) * col_w, 40 + (i // cols) * 24
        body.append(swatch(cx, y - 9, 10, COLORS.get(lang, OTHER), t))
        body.append(text(cx + 18, y, lang, 12, t["fg"]))
        body.append(text(cx + col_w - 28, y, f"{share * 100:.1f}%", 12, t["muted"], anchor="end"))
    return svg(WIDTH, height, "Languages", "\n".join(body))


# -- README sections -----------------------------------------------------------

def attr(value):
    return escape(value, {'"': "&quot;"})


def picture(path, alt, width=None, tooltip=False):
    """<picture> for dist/<path>-{light,dark}.svg as published on the output branch;
    with tooltip, the alt text also shows on hover."""
    extra = (f' width="{width}"' if width else "") + (f' title="{attr(alt)}"' if tooltip else "")
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{IMAGES}{path}-dark.svg">'
            f'<img src="{IMAGES}{path}-light.svg"{extra} align="top" alt="{attr(alt)}"></picture>')


def shelf_html():
    # Inside <pre> whitespace shows: each shelf row is one line, and tags only
    # break lines inside themselves.
    rows = ["".join(f'<a\nhref="https://github.com/{USER}/{name}">'
                    f'{picture(f"projects/{name}", f"{name}: {desc}", CARD_W + CARD_GAP, tooltip=True)}</a>'
                    for name, _, desc in PROJECTS[row::SHELF_ROWS])
            for row in range(SHELF_ROWS)]
    return "<pre>" + "\n".join(rows) + "</pre>"


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def grid_blocks(columns):
    """The fork grid top to bottom, as (row_major, categories): column blocks of
    up to COLUMNS categories side by side, then one block per ROW_MAJOR category."""
    side = [c for c in columns if c[0] not in ROW_MAJOR]
    wide = sorted((c for c in columns if c[0] in ROW_MAJOR), key=lambda c: ROW_MAJOR.index(c[0]))
    return [(False, side[i:i + COLUMNS]) for i in range(0, len(side), COLUMNS)] + [(True, [c]) for c in wide]


def grid_html(blocks, upstreams):
    width = f"{100 / COLUMNS:g}%"
    # Fills empty cells, so every row spans COLUMNS tiles; 1px tall, so it never sets a row's height.
    blank = f'<picture><img src="{IMAGES}forks/blank.svg" width="{width}" align="top" alt=""></picture>'

    def tile(name):
        upstream = upstreams.get(name)
        alt = f"{name}, a fork of {upstream}" if upstream else name
        return f'<a href="https://github.com/{USER}/{name}">{picture(f"forks/{name}", alt, width, tooltip=True)}</a>'

    tiles = []
    for row_major, block in blocks:
        if row_major:
            (title, repos), = block
            tiles += [picture(f"forks/_{slug(title)}", title, width)] + [blank] * (COLUMNS - 1)
            for i in range(0, len(repos), COLUMNS):
                row = repos[i:i + COLUMNS]
                tiles += [tile(name) for name in row] + [blank] * (COLUMNS - len(row))
            continue
        pad = [blank] * (COLUMNS - len(block))
        tiles += [picture(f"forks/_{slug(title)}", title, width) for title, _ in block] + pad
        for row in range(max(len(repos) for _, repos in block)):
            tiles += [tile(repos[row]) if row < len(repos) else blank for _, repos in block] + pad
    # Tiles must touch: break lines after a tag name rather than between tags.
    return "<p>" + "".join(re.sub(r"^<(\w+)", "<\\1\n", tile) for tile in tiles) + "</p>"


def readme_md(columns, upstreams, shares):
    stack = ". ".join(f"{label}: {', '.join(name for name, _ in items)}" for label, items in STACK)
    snake = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{IMAGES}snake-dark.svg">'
             f'<img src="{IMAGES}snake.svg" width="100%" align="top" '
             'alt="Animated snake following the GitHub contribution calendar"></picture>')
    blocks = [
        "<!-- Generated by scripts/render.py; edit that instead. -->",
        picture("name", NAME, "100%"),
        f"<samp>{MOTTO}</samp>",
        picture("stack", stack, "100%"),
        picture("section-projects", "Projects", "100%"),
        shelf_html(),
        picture("section-forks", "Forks", "100%"),
        grid_html(grid_blocks(columns), upstreams),
        picture("section-languages", "Languages", "100%"),
        picture("languages", "Languages by code size: " + (", ".join(lang for lang, _ in shares) or "no public data"), "100%"),
        picture("section-contributions", "GitHub Contributions", "100%"),
        snake,
    ]
    return "\n\n".join(blocks) + "\n"


# -- GitHub API ----------------------------------------------------------------

def get(url, attempts=4):
    """GET a GitHub API URL as JSON, retrying network errors, 5xx and rate limits."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code < 500 and err.code not in (403, 429) or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
        time.sleep(2 ** attempt)


def owned_repos():
    repos, page = [], 1
    while True:
        batch = get(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("Invalid public repository response")
        for repo in batch:
            if repo.get("private") is not False:
                raise ValueError("PRIVATE_REPOSITORY_VISIBLE: refusing to publish private metadata")
            if repo.get("owner", {}).get("login", "").lower() == USER.lower():
                repos.append(repo)
        if len(batch) < 100:
            return repos
        page += 1


def warn(message):
    print(f"warning: {message}")


def public_projects(owned):
    return {r["name"]: r for r in owned
            if r.get("private") is False and not r["fork"]
            and r["owner"]["login"].lower() == USER.lower()
            and r["name"].lower() != USER.lower()}


def fork_columns(forks):
    """FORKS limited to the given fork names, plus a column for the ones it misses."""
    listed = {name for _, names in FORKS for name in names}
    for name in sorted(listed - forks, key=str.lower):
        warn(f"{name} is in FORKS but is not a fork of {USER}; skipped")
    columns = [(title, [n for n in names if n in forks]) for title, names in FORKS]
    columns = [(title, names) for title, names in columns if names]
    unlisted = sorted(forks - listed, key=str.lower)
    if unlisted:
        warn(f"not in FORKS, shown as Uncategorized: {', '.join(unlisted)}")
        columns.append(("Uncategorized", unlisted))
    return columns


def fork_status(name):
    """Return the API parent and commits missing from the fork's default branch.

    With the fork as comparison base and upstream as head, GitHub's ahead_by
    counts upstream commits absent from the fork. Failure stays unknown, not 0.
    """
    upstream = None
    try:
        repo = get(f"https://api.github.com/repos/{USER}/{name}")
        if (not isinstance(repo, dict) or repo.get("private") is not False or repo.get("fork") is not True
                or repo.get("owner", {}).get("login", "").lower() != USER.lower()):
            raise ValueError("unexpected public fork metadata")
        parent = repo["parent"]
        if not isinstance(parent, dict) or parent.get("private") is not False:
            raise ValueError("upstream is not public")
        upstream = parent["full_name"]
        head = f"{parent['owner']['login']}:{parent['default_branch']}"
        comparison = get(
            f"https://api.github.com/repos/{USER}/{name}/compare/"
            f"{urllib.parse.quote(repo['default_branch'], safe='')}..."
            f"{urllib.parse.quote(head, safe=':')}")
        behind = comparison["ahead_by"]
        if not isinstance(behind, int) or isinstance(behind, bool) or behind < 0:
            raise ValueError("invalid upstream commit count")
        return upstream, behind
    except (urllib.error.URLError, ConnectionError, KeyError, TypeError, ValueError, TimeoutError) as error:
        warn(f"no sync status for {name}: {error!r}")
        return upstream, None


def language_shares(repos):
    totals = {}
    for repo in repos:
        # Construct the endpoint from the known public owner/name.
        for lang, size in get(f"https://api.github.com/repos/{USER}/{repo['name']}/languages").items():
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError("Invalid language byte count")
            totals[lang] = totals.get(lang, 0) + size
    ranked = sorted(((lang, size) for lang, size in totals.items() if size), key=lambda kv: (-kv[1], kv[0]))
    total = sum(totals.values())
    if not total:
        return []
    shares = [(lang, size / total) for lang, size in ranked[:TOP_LANGUAGES]]
    rest = sum(size for _, size in ranked[TOP_LANGUAGES:])
    if rest:
        shares.append(("Other", rest / total))
    return shares


def render(owned):
    repos = public_projects(owned)
    for name, _, _ in PROJECTS:
        if name not in repos:
            raise ValueError(f"{name} is not a public non-fork repository of {USER}")
    shares = language_shares(repos.values())
    columns = fork_columns({r["name"] for r in owned
                            if r.get("private") is False and r.get("fork") is True
                            and r.get("owner", {}).get("login", "").lower() == USER.lower()})
    fork_names = [name for _, names in columns for name in names]
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = dict(zip(fork_names, pool.map(fork_status, fork_names)))
    upstreams = {name: upstream for name, (upstream, _) in statuses.items()}
    behind = {name: count for name, (_, count) in statuses.items()}
    blocks = grid_blocks(columns)
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    outputs = {}
    for theme, t in THEMES.items():
        outputs[f"name-{theme}.svg"] = render_name(t)
        outputs[f"stack-{theme}.svg"] = render_stack(t)
        project_hint = "SCROLL →" if len(PROJECTS) > 2 else ""
        outputs[f"section-projects-{theme}.svg"] = render_section("Projects", len(PROJECTS), project_hint, t)
        outputs[f"section-forks-{theme}.svg"] = render_section(
            "Forks", len(fork_names), f"COMMITS BEHIND UPSTREAM · {today}", t, hint_icon="arrow-down")
        outputs[f"section-languages-{theme}.svg"] = render_section(
            "Languages", None, f"BY CODE SIZE · {len(repos)} REPOS", t)
        outputs[f"languages-{theme}.svg"] = render_languages(shares, t)
        outputs[f"section-contributions-{theme}.svg"] = render_section(
            "GitHub Contributions", None, "LAST 12 MONTHS", t)
        for i, (name, area, desc) in enumerate(PROJECTS):
            gap_below = i % SHELF_ROWS < SHELF_ROWS - 1
            outputs[f"projects/{name}-{theme}.svg"] = render_project(
                name, area, desc, repos[name], gap_below, t)
        for block_index, (_, block) in enumerate(blocks):
            for title, forks in block:
                outputs[f"forks/_{slug(title)}-{theme}.svg"] = render_fork_heading(
                    title, len(forks), HEADING_H[block_index > 0], t)
                for name in forks:
                    outputs[f"forks/{name}-{theme}.svg"] = render_fork(name, behind[name], t)
    readme = readme_md(columns, upstreams, shares)
    if f"{IMAGES}forks/blank.svg" in readme:
        outputs["forks/blank.svg"] = svg(TILE_W, 1, "", "")
    return outputs, readme


def main():
    # Finish API requests and rendering before replacing local generated files.
    outputs, readme = render(owned_repos())
    BUILD.mkdir(parents=True, exist_ok=True)
    for rel, content in outputs.items():
        path = BUILD / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # Only files in this manifest are published; stale images and API snapshots stay local.
    (BUILD / "assets.json").write_text(json.dumps(sorted([*outputs, *SNAKES]), indent=2) + "\n", encoding="utf-8")
    README.write_text(readme, encoding="utf-8")
    print(f"Rendered {len(outputs)} SVGs into {BUILD.name}/ and wrote {README.name}.")


if __name__ == "__main__":
    main()
