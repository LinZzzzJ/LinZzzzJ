import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

export const LOGIN = 'LinZzzzJ';
const API = 'https://api.github.com';
const QUERY = `query PublicActivity($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    contributionsCollection(from: $from, to: $to) {
      restrictedContributionsCount
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}`;

const number = (value, name) => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`Invalid activity count: ${name}`);
  return value;
};

export function validateActivity(body, login = LOGIN) {
  if (body.errors?.length) throw new Error(`GitHub query failed: ${body.errors.map(e => e.message).join('; ')}`);
  const user = body.data?.user;
  if (!user || user.login.toLowerCase() !== login.toLowerCase()) throw new Error('Unexpected GitHub account.');
  const collection = user.contributionsCollection;
  if (!collection) throw new Error('Missing contribution collection.');
  const restrictedContributions = number(collection.restrictedContributionsCount, 'restrictedContributionsCount');
  const calendar = collection.contributionCalendar;
  if (!Array.isArray(calendar?.weeks)) throw new Error('Missing public contribution calendar.');
  const seen = new Set();
  const days = calendar.weeks.flatMap(week => {
    if (!Array.isArray(week.contributionDays)) throw new Error('Invalid calendar week.');
    return week.contributionDays.map(day => {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(day.date) || seen.has(day.date)) throw new Error('Invalid or duplicate calendar date.');
      seen.add(day.date);
      if (!Number.isInteger(day.weekday) || day.weekday < 0 || day.weekday > 6) throw new Error('Invalid weekday.');
      return { date: day.date, count: number(day.contributionCount, 'day contributionCount') };
    });
  });
  const contributions = number(calendar.totalContributions, 'totalContributions');
  if (days.reduce((sum, day) => sum + day.count, 0) !== contributions) throw new Error('Calendar totals do not match daily public counts.');
  if (restrictedContributions > contributions) throw new Error('Restricted contributions exceed calendar total.');
  return {
    commits: number(collection.totalCommitContributions, 'commits'),
    prs: number(collection.totalPullRequestContributions, 'pull requests'),
    issues: number(collection.totalIssueContributions, 'issues'),
    contributions,
    restrictedContributions,
    days,
    activeDays: days.filter(day => day.count > 0).length
  };
}

export async function collectPublicData({ token, login = LOGIN, now = new Date(), fetchImpl = fetch, window }) {
  if (!token) throw new Error('The workflow GITHUB_TOKEN is required.');
  const end = new Date(now);
  const start = new Date(end);
  start.setUTCFullYear(start.getUTCFullYear() - 1);
  const period = window ?? { from: start.toISOString(), to: end.toISOString() };
  async function request(path, payload) {
    let response;
    for (let attempt = 0; attempt < 3; attempt++) {
      response = await fetchImpl(API + path, {
        method: payload ? 'POST' : 'GET',
        headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28' },
        ...(payload ? { body: JSON.stringify(payload) } : {}),
        signal: AbortSignal.timeout(30000)
      });
      if (response.status < 500 || attempt === 2) break;
      await new Promise(accept => setTimeout(accept, 1000 * (attempt + 1)));
    }
    if (!response.ok) throw new Error(`GitHub activity-data request failed (HTTP ${response.status}).`);
    return response.json();
  }
  const body = await request('/graphql', { query: QUERY, variables: { login, ...period } });
  const activity = validateActivity(body, login);
  let stars = 0;
  for (let page = 1; ; page++) {
    const repos = await request(`/users/${encodeURIComponent(login)}/repos?type=owner&per_page=100&page=${page}`);
    if (!Array.isArray(repos)) throw new Error('Invalid public-repository response.');
    for (const repo of repos) {
      if (repo.private !== false) throw new Error('PRIVATE_REPOSITORY_VISIBLE: refusing to publish private metadata.');
      if (!repo.fork && repo.owner?.login?.toLowerCase() === login.toLowerCase()) {
        stars += number(repo.stargazers_count, 'public stars');
      }
    }
    if (repos.length < 100) break;
  }
  return { login, displayName: 'LinZzJ', updatedAt: end.toISOString(), window: period, stars, ...activity };
}

async function main() {
  if (process.env.GITHUB_ACTIONS !== 'true' || process.env.GITHUB_REPOSITORY !== `${LOGIN}/${LOGIN}`) {
    throw new Error('Live data collection is restricted to this public profile workflow and its own GITHUB_TOKEN.');
  }
  const command = process.argv[2];
  const dist = resolve('dist');
  const snapshot = join(dist, 'public-data.json');
  const options = { token: process.env.GITHUB_TOKEN, login: LOGIN };
  if (command === 'collect') {
    const data = await collectPublicData(options);
    await mkdir(dist, { recursive: true });
    await writeFile(snapshot, JSON.stringify(data, null, 2));
    console.log(`GitHub activity snapshot collected: ${data.contributions} contributions, ${data.activeDays} active days (${data.restrictedContributions} anonymous private).`);
  } else if (command === 'verify') {
    const saved = JSON.parse(await readFile(snapshot, 'utf8'));
    await collectPublicData({ ...options, window: saved.window });
    console.log('GitHub activity visibility verified again; complete assets may be published.');
  } else {
    throw new Error('Usage: node scripts/profile.mjs collect|verify');
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
