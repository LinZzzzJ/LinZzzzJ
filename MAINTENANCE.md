# Maintaining this profile

This public repository contains only the profile introduction, original toolkit icons, generation scripts and workflow. Research code and experimental data are not stored here.

## Editing

Edit `README.md` to change the introduction. Keep the existing light/dark `<picture>` elements so both GitHub themes work. With Node.js 24 installed, run `npm test` before pushing script changes. The scripts use only built-in Node.js modules; no package installation is required.

The README separates engineering interests, selected work and the toolkit. FitTrack is a public project; its listed software stack is checked against its public README, `pyproject.toml`, frontend `package.json` and GitHub language data. Embedded and hardware topics reflect the owner's stated engineering interests. The local SVG tiles are original, consistent illustrations of those technologies, not official logos or proficiency ratings. Keep private research descriptions general and do not add private repository links or experimental information.

## Automatic updates

The **Update public profile visuals** workflow runs daily at **03:17 UTC / 11:17 Asia/Shanghai**, and can be run from **Actions → Update public profile visuals → Run workflow**. GitHub schedules may run late or be paused after prolonged repository inactivity; use the manual trigger to check or resume updates.

The workflow generates two statistics cards and two [Platane/snk](https://github.com/Platane/snk) contribution-snake SVGs. All four assets are published together to the `output` branch. Bot-generated images do not modify the hand-written README. Unchanged assets do not create a new commit. Failed generation leaves the last complete asset set intact.

## Public data only

- **Stars** sums current stars on public, non-fork repositories owned by this account.
- **Commits, PRs, Issues and Contributions** use GitHub's public contribution records for the trailing twelve-month period displayed on the card. Contributions include GitHub-counted activities beyond commits.
- The ring shows active public-contribution days divided by the number of days returned in that period. It is not a developer grade.
- No personal access token or private-repository credential is configured in this repository. The workflow uses its own `GITHUB_TOKEN`.
- If GitHub returns anonymous private contributions, the workflow fails before publishing. Open the profile's **Contribution settings → Private contributions**, turn that option **off**, then run the workflow again. The private-repository names and their activity counts must not be published here.

An empty public history is valid and displays zero activity. Uploading a private project does not fill this public calendar. Commit dates are never synthesized or backdated.

## Generated files

Only `assets/stats-light.svg`, `assets/stats-dark.svg`, `assets/snake.svg`, and `assets/snake-dark.svg` are placed on `output`. Intermediate API responses are not published. The main branch contains no generated activity data. Action dependencies are pinned to reviewed release commits.
