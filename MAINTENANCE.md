# Maintaining this profile

This is the source of LinZzzzJ's GitHub profile README. The layout is adapted from
`~/projects/zeroherolin`: the same 840px SVG canvas, typography, light/dark palettes,
section rules, project shelf, language chart and four-column fork tiles.

## Editing and previewing

Edit the name, motto, `STACK`, `PROJECTS` and `FORKS` in `scripts/render.py`, then run:

```sh
python3 scripts/render.py
npm test
```

Python 3.10+ and Node.js 24+ are required. Both scripts use only their standard
libraries; no package installation is required. Local rendering reads GitHub's
public REST API; an optional `GITHUB_TOKEN` increases the API rate limit.

`README.md` is generated. The renderer writes themed images and `assets.json` to
the ignored `dist/` directory. README image URLs point to the `output` branch, so
new visuals become visible on GitHub after the workflow publishes them. Local
SVGs can be opened directly for inspection.

The name is **LinZzzzJ**. The introduction is **Think Deep. Automate the Rest.**
The skills rows retain the existing languages, SQLite, hardware platforms and
workflow tools, remove PowerShell, Svelte, FastAPI, ECharts, HDF5 and Windows, and
add PI/SI simulation, high-speed signals, PCIe, USB and MIPI. Do not add private
research links or experimental information.

The **Forks** section uses the reference project's display rules. `FORKS` maps
category names to this account's fork repository names, in display order. The
**AI AGENTS** category contains **dsh-purge**; **VIBECODING APP** contains
**openGym_FitTrack**. Cards link to this account's forks; categories show their
project counts. No repositories are copied from the reference account's
configuration.

Each category occupies one of four columns and lists its forks vertically. Empty
categories are hidden; configured repositories no longer present as public forks
are skipped with a warning. New public forks not listed in `FORKS` appear in
**Uncategorized**, sorted by name. **Learning** and **Uncategorized** fill four
columns row by row after the other categories. Transparent 1px padding fills
unused cells without drawing empty cards.

The Forks section shows its total count and the update date in China Standard
Time. Each card compares its default branch against its API-reported parent's
default branch: a check means no missing upstream commits, a down arrow and
number show commits behind, and a cross means status could not be fetched.
Being ahead does not prevent a check when no upstream commits are missing. A
missing parent or failed comparison keeps the card and logs a warning instead of
displaying a false zero. The upstream name in the tooltip comes from GitHub's
`parent` metadata, not the repository description. This does not sync or modify
any fork's code.

The old colored toolkit tiles remain available under `assets/icons/`. The new
monochrome glyphs are under `assets/icons/mono/`: the star, fork, Linux and status
glyphs come from the reference project; Svelte, FastAPI, Git and Node.js are from
[Simple Icons](https://github.com/simple-icons/simple-icons) v16 (CC0); the small
data, hardware and Windows symbols are original vector drawings.

## Automatic updates

**Update public profile visuals** runs daily at **03:17 UTC / 11:17 Asia/Shanghai**,
on relevant source changes, and from **Actions → Update public profile visuals →
Run workflow**. GitHub schedules may run late or pause after repository inactivity;
the manual trigger can resume updates.

The workflow tests the scripts, validates a contribution snapshot, renders the
profile images and README, generates both contribution snakes using
[Platane/snk](https://github.com/Platane/snk), and rechecks contribution visibility.
It then publishes the complete SVG set to `output` and commits README changes to
`main`. README-only bot commits do not trigger the workflow again.

Images are stored beneath `assets/` on `output`. Both existing snake URLs remain
unchanged (`assets/snake.svg`, `assets/snake-dark.svg`), including their purple
snake colors. The old statistics cards are no longer generated or published.

The publisher reads `dist/assets.json`, verifies that it matches the generated
README's image references, validates every listed SVG, and updates the output
branch in one commit. Missing images or generation failures leave the previous
published assets intact. Identical assets create no commit. Unlisted stale files
and intermediate API responses are never published.

## Public data and contribution counts

- Language shares use GitHub's byte counts across public, owned, non-fork
  repositories, excluding the profile repository. The largest seven languages
  are shown individually and the remainder as **Other**. Empty language data
  displays an empty state; failed API requests stop generation.
- Project card numbers and fork synchronization statuses use current public
  repository data. The daily run discovers new public forks automatically;
  running the workflow manually displays them sooner.
- The snake follows the trailing-year contribution calendar. Private activity,
  when enabled on the profile, is included only as anonymous contribution counts.
  Contribution dates are never synthesized or backdated.
- The workflow uses its own `GITHUB_TOKEN`; no personal access token or private
  repository credential is needed. Public repository collection rejects private
  metadata. Contribution snapshots and API responses stay local to the workflow.
- The activity collector retries transient network failures, HTTP 429 responses
  and server errors up to three times. A final network failure names the endpoint
  and underlying network error code when Node.js provides one.

Run `npm test` after changing the renderer, activity collector or publisher. Tests
cover theme/layout output, fork grouping and synchronization, XML escaping,
public data selection, empty language data, API failure, anonymous contribution
validation and atomic publication to a temporary local Git remote. They never
publish to GitHub.
