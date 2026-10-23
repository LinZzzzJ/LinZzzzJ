# Maintaining this profile

This is the source of LinZzzzJ's GitHub profile README. The layout is adapted from
`~/projects/zeroherolin`: the same 840px SVG canvas, typography, light/dark palettes,
section rules, project shelf, language chart and four-column fork tiles.

## Editing and previewing

Edit the name, motto, `STACK` and `PROJECTS` in `scripts/render.py`, then run:

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

The name is **LinZzJ**. The only introduction is
**把真实问题研究清楚，把重复工作交给工具。** All existing skills remain in four compact
rows: languages, apps/data, hardware and workflow. FitTrack is the only selected
project. Its short English description is curated, while its language, stars and
forks come from public repository metadata. Do not add private research links or
experimental information.

The **Forks** section intentionally contains four empty tiles. Do not populate
them automatically, add categories, or copy the reference account's forks. The
owner will confirm repositories and ordering later.

The old colored toolkit tiles remain available under `assets/icons/`. The new
monochrome glyphs are under `assets/icons/mono/`: the star, fork and Linux glyphs
come from the reference project; Svelte, FastAPI, Git and Node.js are from
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
- Project card numbers are current public repository data. Forks stay reserved
  even if new forks appear on the account.
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
cover theme/layout output, XML escaping, public data selection, empty language
data, API failure, anonymous contribution validation and atomic publication to a
temporary local Git remote. They never publish to GitHub.
