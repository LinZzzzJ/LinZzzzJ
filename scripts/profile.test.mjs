import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { validateActivity, collectPublicData, LOGIN } from './profile.mjs';
import { publishAssets, SNAKE_ASSETS } from './publish-assets.mjs';

const collection = (counts = [0, 2, 3]) => ({ data: { user: { login: LOGIN, contributionsCollection: {
  restrictedContributionsCount: 0, totalCommitContributions: 3, totalPullRequestContributions: 1,
  totalIssueContributions: 1, contributionCalendar: {
    totalContributions: counts.reduce((a, b) => a + b, 0),
    weeks: [{ contributionDays: counts.map((n, i) => ({ date: `2026-10-${18 + i}`, contributionCount: n, weekday: i })) }]
  }
} } } });

test('anonymous private contributions are accepted as aggregate activity', () => {
  const body = collection();
  body.data.user.contributionsCollection.restrictedContributionsCount = 1;
  const activity = validateActivity(body);
  assert.equal(activity.restrictedContributions, 1);
  assert.equal(activity.contributions, 5);
  body.data.user.contributionsCollection.restrictedContributionsCount = 6;
  assert.throws(() => validateActivity(body), /exceed calendar total/);
});

test('contribution calendar validates totals, dates, nonnegative counts and API errors', () => {
  assert.equal(validateActivity(collection()).activeDays, 2);
  const zero = validateActivity(collection([0, 0])); assert.equal(zero.contributions, 0);
  assert.throws(() => validateActivity({ errors: [{ message: 'fixture error' }] }), /fixture error/);
  const bad = collection(); bad.data.user.contributionsCollection.contributionCalendar.totalContributions++;
  assert.throws(() => validateActivity(bad), /do not match/);
  const dup = collection(); dup.data.user.contributionsCollection.contributionCalendar.weeks[0].contributionDays[1].date = '2026-10-18';
  assert.throws(() => validateActivity(dup), /duplicate/);
});

test('stars paginate, exclude forks and other owners, and reject private metadata', async () => {
  const repos = Array.from({ length: 100 }, () => ({ private: false, fork: false, owner: { login: LOGIN }, stargazers_count: 1 }));
  repos[0].fork = true; repos[1].owner = { login: 'someone-else' };
  let n = 0;
  const data = await collectPublicData({ token: 'fixture', now: new Date('2026-10-20T03:17:00Z'), fetchImpl: async () => {
    n++; return { ok: true, status: 200, json: async () => n === 1 ? collection() : n === 2 ? repos : [{ private: false, fork: false, owner: { login: LOGIN }, stargazers_count: 7 }] };
  } });
  assert.equal(data.stars, 105); assert.equal(n, 3);
  assert.equal(data.window.from, '2025-10-20T03:17:00.000Z');
  let i = 0;
  await assert.rejects(collectPublicData({ token: 'fixture', fetchImpl: async () => ({ ok: true, status: 200, json: async () => ++i === 1 ? collection() : [{ private: true }] }) }), /PRIVATE_REPOSITORY_VISIBLE/);
});

test('atomic Git publication preserves main and old assets on failure; identical files create no commit', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'profile-git-test-'));
  try {
    const remote = join(dir, 'remote.git'), work = join(dir, 'work');
    await mkdir(work);
    const git = (args, cwd = work) => execFileSync('git', args, { cwd, encoding: 'utf8', windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    git(['init', '--bare', remote]); git(['init', '--initial-branch=main']);
    git(['config', 'user.name', 'Fixture']); git(['config', 'user.email', 'fixture@example.invalid']);
    const assets = [...SNAKE_ASSETS, 'name-light.svg', 'name-dark.svg', 'projects/FitTrack-light.svg', 'projects/FitTrack-dark.svg'];
    const readme = 'Generated profile.\n' + assets.map(file =>
      `<img src="https://raw.githubusercontent.com/LinZzzzJ/LinZzzzJ/output/assets/${file}">`).join('\n');
    await writeFile(join(work, 'README.md'), readme);
    git(['add', 'README.md']); git(['commit', '-m', 'fixture']); git(['remote', 'add', 'origin', remote]); git(['push', '-u', 'origin', 'main']);
    const main = git(['rev-parse', 'HEAD']); const dist = join(work, 'dist'); await mkdir(dist);
    await mkdir(join(dist, 'projects'));
    const fixture = '<svg xmlns="http://www.w3.org/2000/svg"><text>public fixture</text></svg>\n';
    for (const name of assets) await writeFile(join(dist, name), fixture);
    await writeFile(join(dist, 'assets.json'), JSON.stringify(assets));
    // Old cards and intermediate metadata must never enter the published tree.
    await writeFile(join(dist, 'stats-light.svg'), fixture);
    await writeFile(join(dist, 'public-data.json'), '{"private":"local-only"}');
    const first = await publishAssets({ cwd: work, dist }); assert.equal(first.changed, true);
    const list = git(['--git-dir=' + remote, 'ls-tree', '-r', '--name-only', 'output']).split('\n');
    assert.deepEqual(list, assets.map(n => 'assets/' + n).sort());
    const second = await publishAssets({ cwd: work, dist }); assert.equal(second.changed, false); assert.equal(second.commit, first.commit);
    assert.equal(git(['rev-parse', 'HEAD']), main);
    assert.equal(git(['--git-dir=' + remote, 'log', '-1', '--format=%an', 'output']), 'github-actions[bot]');
    await writeFile(join(dist, 'snake.svg'), '<svg><script>bad</script></svg>');
    await assert.rejects(publishAssets({ cwd: work, dist }), /Invalid/);
    assert.equal(git(['--git-dir=' + remote, 'rev-parse', 'output']), first.commit);
    assert.equal(await readFile(join(work, 'README.md'), 'utf8'), readme);
    await writeFile(join(dist, 'snake.svg'), fixture);
    await rm(join(dist, 'projects/FitTrack-dark.svg'));
    await assert.rejects(publishAssets({ cwd: work, dist }), /ENOENT/);
    await writeFile(join(dist, 'projects/FitTrack-dark.svg'), fixture);
    await writeFile(join(dist, 'assets.json'), JSON.stringify(assets.filter(file => file !== 'name-dark.svg')));
    await assert.rejects(publishAssets({ cwd: work, dist }), /README references/);
    await writeFile(join(dist, 'assets.json'), JSON.stringify([...assets, '../secret.svg']));
    await assert.rejects(publishAssets({ cwd: work, dist }), /Invalid/);
    await writeFile(join(dist, 'assets.json'), JSON.stringify(assets.filter(file => file !== 'snake-dark.svg')));
    await assert.rejects(publishAssets({ cwd: work, dist }), /incomplete/);
    assert.equal(git(['--git-dir=' + remote, 'rev-parse', 'output']), first.commit);
  } finally { await rm(dir, { recursive: true, force: true }); }
});
