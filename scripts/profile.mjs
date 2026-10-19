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
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`Invalid public count: ${name}`);
  return value;
};

export function validateActivity(body, login = LOGIN) {
  if (body.errors?.length) throw new Error(`GitHub query failed: ${body.errors.map(e => e.message).join('; ')}`);
  const user = body.data?.user;
  if (!user || user.login.toLowerCase() !== login.toLowerCase()) throw new Error('Unexpected GitHub account.');
  const collection = user.contributionsCollection;
  if (!collection) throw new Error('Missing contribution collection.');
  if (number(collection.restrictedContributionsCount, 'restrictedContributionsCount') !== 0) {
    throw new Error('PRIVATE_CONTRIBUTIONS_VISIBLE: turn OFF profile → Contribution settings → Private contributions, then rerun. No images were published.');
  }
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
  return {
    commits: number(collection.totalCommitContributions, 'commits'),
    prs: number(collection.totalPullRequestContributions, 'pull requests'),
    issues: number(collection.totalIssueContributions, 'issues'),
    contributions,
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
    if (!response.ok) throw new Error(`GitHub public-data request failed (HTTP ${response.status}).`);
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

export const escapeXml = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c]);

export function renderStats(data, dark = false) {
  const colors = dark
    ? { background: '#0d1117', border: '#30363d', text: '#c9d1d9', muted: '#8b949e', blue: '#79c0ff', ring: '#1f6feb' }
    : { background: '#ffffff', border: '#d0d7de', text: '#434d58', muted: '#6e7781', blue: '#2f80ed', ring: '#cfe1ff' };
  const rows = [['Public Stars', data.stars], ['Public Commits', data.commits], ['Public PRs', data.prs], ['Public Issues', data.issues], ['Public Contributions', data.contributions]];
  for (const [label, value] of rows) number(value, label);
  const totalDays = data.days.length;
  const activeDays = number(data.activeDays, 'activeDays');
  if (activeDays > totalDays) throw new Error('Active-day count exceeds calendar size.');
  const radius = 38, circumference = 2 * Math.PI * radius;
  const fraction = totalDays ? activeDays / totalDays : 0;
  const updated = new Date(data.updatedAt).toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai', hour12: false }).slice(0, 16);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="450" height="224" viewBox="0 0 450 224" role="img" aria-labelledby="title desc">
  <title id="title">${escapeXml(data.displayName)}'s GitHub Stats — public activity</title>
  <desc id="desc">Stars: public owned non-fork repositories. Activity: trailing twelve months. Active public days: ${activeDays}/${totalDays}. No private activity.</desc>
  <rect x=".5" y=".5" width="449" height="223" rx="6" fill="${colors.background}" stroke="${colors.border}"/>
  <g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">
    <text x="24" y="33" fill="${colors.blue}" font-size="18" font-weight="600">${escapeXml(data.displayName)}'s GitHub Stats</text>
    <text x="24" y="53" fill="${colors.muted}" font-size="10">Public activity · last 12 months</text>
    ${rows.map(([label, value], i) => `<g transform="translate(24 ${78 + 23 * i})"><circle cx="5" cy="-4" r="3" fill="${colors.blue}"/><text x="20" fill="${colors.text}" font-size="12" font-weight="600">${label}:</text><text x="239" text-anchor="end" fill="${colors.text}" font-size="12" font-weight="600">${new Intl.NumberFormat('en-US').format(value)}</text></g>`).join('\n    ')}
    <g transform="translate(359 117)">
      <circle r="${radius}" fill="none" stroke="${colors.ring}" stroke-width="6"/>
      <circle r="${radius}" fill="none" stroke="${colors.blue}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${fraction * circumference} ${circumference}" transform="rotate(-90)"/>
      <text y="-2" fill="${colors.text}" text-anchor="middle" font-size="23" font-weight="700">${activeDays}<tspan font-size="11" font-weight="400">d</tspan></text>
      <text y="16" fill="${colors.muted}" text-anchor="middle" font-size="9">active public days</text>
    </g>
    <text x="24" y="202" fill="${colors.muted}" font-size="9">Stars: current · Activity: ${escapeXml(data.window.from.slice(0, 10))}–${escapeXml(data.window.to.slice(0, 10))}</text>
    <text x="24" y="216" fill="${colors.muted}" font-size="9">Updated ${escapeXml(updated)} (UTC+8)</text>
  </g>
</svg>\n`;
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
    await writeFile(join(dist, 'stats-light.svg'), renderStats(data));
    await writeFile(join(dist, 'stats-dark.svg'), renderStats(data, true));
    await writeFile(snapshot, JSON.stringify(data, null, 2));
    console.log(`Public-only snapshot collected: ${data.contributions} contributions, ${data.activeDays} active days.`);
  } else if (command === 'verify') {
    const saved = JSON.parse(await readFile(snapshot, 'utf8'));
    await collectPublicData({ ...options, window: saved.window });
    console.log('Public-only visibility verified again; complete assets may be published.');
  } else {
    throw new Error('Usage: node scripts/profile.mjs collect|verify');
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
