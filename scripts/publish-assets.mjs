import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export const SNAKE_ASSETS = ['snake.svg', 'snake-dark.svg'];

async function assetManifest(cwd, dist) {
  const files = JSON.parse(await readFile(join(dist, 'assets.json'), 'utf8'));
  if (!Array.isArray(files) || !files.length || new Set(files).size !== files.length ||
      files.some(file => typeof file !== 'string' ||
        !/^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*\.svg$/.test(file)) ||
      SNAKE_ASSETS.some(file => !files.includes(file))) {
    throw new Error('Invalid or incomplete SVG asset manifest.');
  }
  const readme = await readFile(join(cwd, 'README.md'), 'utf8');
  const references = [...readme.matchAll(/https:\/\/raw\.githubusercontent\.com\/[^/]+\/[^/]+\/output\/assets\/([^"\s<>]+\.svg)/g)]
    .map(match => match[1]);
  if (!references.length || references.some(file => !files.includes(file)) ||
      files.some(file => !references.includes(file))) {
    throw new Error('README references and the SVG asset manifest do not match.');
  }
  return files.sort();
}

export async function publishAssets({ cwd = process.cwd(), dist = resolve(cwd, 'dist') } = {}) {
  const files = await assetManifest(cwd, dist);
  const documents = [];
  for (const file of files) {
    const bytes = await readFile(join(dist, file));
    const text = bytes.toString('utf8');
    if (bytes.length > 5 * 1024 * 1024 || !/<svg\b/i.test(text) || /<script\b|<foreignObject\b|\bonload\s*=|(?:href|src)\s*=\s*["'](?:https?:|data:)/i.test(text)) {
      throw new Error(`Invalid or externally linked generated SVG: ${file}`);
    }
    documents.push([file, bytes]);
  }
  const temp = await mkdtemp(join(process.env.RUNNER_TEMP || tmpdir(), 'public-profile-index-'));
  const env = { ...process.env, GIT_INDEX_FILE: join(temp, 'index'),
    GIT_AUTHOR_NAME: 'github-actions[bot]', GIT_COMMITTER_NAME: 'github-actions[bot]',
    GIT_AUTHOR_EMAIL: '41898282+github-actions[bot]@users.noreply.github.com',
    GIT_COMMITTER_EMAIL: '41898282+github-actions[bot]@users.noreply.github.com' };
  function git(args, input) {
    const result = spawnSync('git', args, { cwd, env, input, encoding: 'utf8', timeout: 90000, windowsHide: true });
    if (result.error) throw result.error;
    if (result.status !== 0) {
      const message = (result.stderr || 'Git command failed.').replaceAll(process.env.GITHUB_TOKEN || '\0', '[redacted]');
      throw new Error(`git ${args[0]}: ${message}`);
    }
    return result.stdout.trim();
  }
  try {
    const remote = git(['ls-remote', '--heads', 'origin', 'refs/heads/output']);
    const parent = remote ? remote.split(/\s+/)[0] : null;
    if (parent) git(['fetch', '--no-tags', 'origin', 'output']);
    git(['read-tree', '--empty']);
    for (const [file, bytes] of documents) {
      const blob = git(['hash-object', '-w', '--stdin'], bytes);
      git(['update-index', '--add', '--cacheinfo', `100644,${blob},assets/${file}`]);
    }
    const tree = git(['write-tree']);
    if (parent && git(['rev-parse', `${parent}^{tree}`]) === tree) {
      console.log('Generated SVGs are unchanged; no bot commit is needed.');
      return { changed: false, commit: parent };
    }
    const commit = git(['commit-tree', tree, ...(parent ? ['-p', parent] : []), '-m', 'chore: update public profile visuals']);
    git(['push', 'origin', `${commit}:refs/heads/output`]);
    console.log(`Published ${documents.length} profile SVGs atomically to output.`);
    return { changed: true, commit };
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  publishAssets().catch(error => { console.error(error.message); process.exitCode = 1; });
}
