/** Sample values for the component gallery and stories only. They are excerpts of real files in
 * examples/monorepo at the commit named below, held inline so no product module, component or
 * domain function depends on a data file. Nothing here is a product observation. */
export interface SampleSkill {
  id: string; name: string; scope: string; owner: string; sourceStatus: string; description: string;
  path: string; revision: string; body: string; raw: string;
}

export const sampleCommit = '88e404561a9f6994cd870743bf858b9b0a616126';
export const sampleRepo = 'monorepo';
export const sampleSourceUrl = (path: string) => 'https://github.com/wiatrM/guidefold/blob/' + sampleCommit + '/examples/monorepo/' + path;

const postgresAuthBody = `# Postgres-backed authorization in turnstile

## When to use / when NOT to use
Use this skill when you:
- change \`platforms/atlas/identity/turnstile/src/auth/middleware.go\` or anything it calls
- add or alter the \`principals\`, \`principal_roles\` or \`decision_cache\` tables
- flip or remove \`legacyAuthMode\` (or any \`config.auth\` key) in \`deploy/deployment.yaml\`
- put a new atlas service behind turnstile

Do NOT use it for:
- writing or testing Rego; that is \`rbac-policies\`, loaded with this skill
- pooling, migrations and failover mechanics; follow \`_root:postgres-production\`

## Decision cache
Cache each allow decision for 30 seconds keyed by principal and resource; never cache a deny.
`;

const postgresAuthRaw = `---
name: postgres-auth
description: "[atlas/identity/turnstile] Add or change authorization checks in the turnstile service."
license: Apache-2.0
metadata:
  scope: atlas.identity.turnstile
  owner: turnstile-team
  status: active
---
${postgresAuthBody}`;

export const sampleSkill: SampleSkill = {
  id: 'urn:skill:meridian:atlas.identity.turnstile:postgres-auth',
  name: 'postgres-auth',
  scope: 'atlas.identity.turnstile',
  owner: 'turnstile-team',
  sourceStatus: 'active',
  description: '[atlas/identity/turnstile] Add or change authorization checks in the turnstile service: bearer-token validation, principal and role lookup in Postgres, RBAC evaluation through the OPA middleware, and the legacyAuthMode flag in deploy/deployment.yaml.',
  path: 'platforms/atlas/identity/turnstile/.agents/skills/postgres-auth/SKILL.md',
  revision: '0f506e5c5bd354754b4ab4244c6992d2819e5266dc10717b97eef693442b214b',
  body: postgresAuthBody,
  raw: postgresAuthRaw,
};

/** A candidate that differs from the source in one line, for diff scenarios. */
export const sampleCandidate = postgresAuthRaw.replace('30 seconds', '60 seconds');

export const sampleSkills: SampleSkill[] = [
  sampleSkill,
  {
    id: 'urn:skill:meridian:_root:adr-process', name: 'adr-process', scope: '_root', owner: 'platform-engineering', sourceStatus: 'active',
    description: '[meridian] How Meridian records architecture decisions as ADRs under docs/adr: numbering, template sections, status lifecycle and who must approve.',
    path: '.agents/skills/adr-process/SKILL.md', revision: 'c00f4a8a0705b17a433b0345a39675879bb558a368a7aa9fd016e00cb83fcda1',
    body: '# ADR process\n\nWrite an ADR when a change crosses a platform boundary or would be expensive to reverse.\n',
    raw: '---\nname: adr-process\nmetadata:\n  scope: _root\n---\n# ADR process\n',
  },
  {
    id: 'urn:skill:meridian:_index:hierarchy-index', name: 'hierarchy-index', scope: '_index', owner: 'platform-engineering', sourceStatus: 'active',
    description: '[meridian] Generated map of all hierarchy nodes, owners and skills. Load once per session when unsure where you are.',
    path: '.agents/skills/hierarchy-index/SKILL.md', revision: '0b491e7bc670958cf135a0978a656c461680b52ae6a23322345d63b411ff6da8',
    body: '# meridian skill hierarchy\n\n## _root (owner: platform-engineering)\n',
    raw: '---\nname: hierarchy-index\nmetadata:\n  scope: _index\n---\n# meridian skill hierarchy\n',
  },
];
