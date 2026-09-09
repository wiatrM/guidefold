// Verbatim excerpt from the repository's Meridian fixture, not generated advice.
export const instruction = [
  '# Conventions specific to this scope',
  '- Tokens are verified with the key set from `libs/auth-sdk`; turnstile never parses JWTs itself.',
  '- Principal lookup is exactly one query joining `principals` and `principal_roles` on the validity window. Any additional query on the request path needs a benchmark in the PR.',
  '- Failure mode is closed: a Postgres or OPA error yields `FORBIDDEN` with `details[0].reason = "auth_backend_unavailable"`, never a pass-through.',
  '- Decisions are logged with `requestId`, `principalId`, `action`, `decision`, `bundleVersion` and `latencyMs`; never log the token or the resource payload.',
].join('\n');

export const github = 'https://github.com/wiatrM/guidefold';
export const demoUrl = 'https://www.youtube.com/watch?v=e350wBr1W8c';
export const fixtureSource =
  'https://github.com/wiatrM/guidefold/blob/main/examples/monorepo/platforms/atlas/identity/turnstile/.agents/skills/postgres-auth/SKILL.md';
