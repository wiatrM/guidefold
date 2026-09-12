/** Where an unauthenticated request is sent, and where it comes back to.
 *
 * Kept apart from LoginRoute.tsx so the shell's session gate can compute the redirect without
 * pulling the login view (and its Panel/RouteState imports) into the management entry chunk.
 */

/** The management route an unauthenticated request falls back to when no target is carried. */
export const DEFAULT_RETURN = '/import';

/**
 * A `return` target is caller-supplied: it arrives in the URL and is handed to the API as
 * `return_to`, which the API 302s to after sign-in. Only a same-origin absolute path is
 * accepted — `//host`, `https://host`, a backslash variant and anything carrying whitespace
 * or a control character fall back to Import instead of becoming an open redirect.
 */
export function safeReturn(raw: string | null | undefined): string {
  if (!raw || raw[0] !== '/' || raw[1] === '/' || raw[1] === '\\') return DEFAULT_RETURN;
  if (/[^ -~]|\\/.test(raw)) return DEFAULT_RETURN;
  // The login page is not somewhere to come back to: a session that just started would be sent
  // to sign in again, and a crafted `?return=/login?return=...` would nest indefinitely.
  if (/^\/login(?:[/?#]|$)/i.test(raw)) return DEFAULT_RETURN;
  return raw;
}

/** The address of the login page carrying `returnTo`; the default target is left implicit. */
export const loginHref = (returnTo: string): string =>
  '/login' + (returnTo && returnTo !== DEFAULT_RETURN ? '?return=' + encodeURIComponent(returnTo) : '');
