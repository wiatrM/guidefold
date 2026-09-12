/** Session gate entry state (IA §3: "Login jest stanem wejścia").
 *
 * Every management route is private. When `/me` is refused the shell sends the request here
 * with the originally requested path in `?return=`, and this page is the only place the hosted
 * UI starts a sign-in. It renders outside the shell: no rail, no organisation context, nothing
 * read from an organisation the caller has not been confirmed a member of.
 *
 * The contract already carries everything this needs: `GET /auth/providers` lists what the API
 * has configured and `GET /auth/login/{provider}?return_to=` starts the redirect (API §4.1).
 * Sign-in finishes at the identity provider and the API 302s back to `return_to`, so there is
 * no in-app "login succeeded" transition to write here.
 */
import { useEffect, useRef, useState } from 'react';
import { ShieldCheckIcon, GithubLogoIcon, GoogleLogoIcon, SignInIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { ActionButton, BrandMark, IconTile, RouteState } from '../Shared';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ApiFailure, asApiError, useAsync } from './apiState';
import type { DataSource } from '../data/source';
import styles from './LoginRoute.module.css';

export {DEFAULT_RETURN, loginHref, safeReturn} from './loginTarget';

const providerIcon = (id: string) => id === 'github'
  ? <GithubLogoIcon weight="regular" aria-hidden="true" />
  : id === 'google' ? <GoogleLogoIcon weight="regular" aria-hidden="true" /> : <SignInIcon weight="regular" aria-hidden="true" />;

export function LoginRoute({ source, returnTo }: { source: DataSource; returnTo: string }) {
  const providers = useAsync(() => source.getAuthProviders(), 'auth-providers');
  const [error, setError] = useState('');
  const main = useRef<HTMLElement>(null);
  // Arriving here is a route change like any other, so the reading position and the keyboard
  // focus move together — the same rule the shell applies to #main on every view change.
  useEffect(() => { document.title = 'Sign in | Guidefold'; window.scrollTo(0, 0); main.current?.focus(); }, []);

  async function signIn(provider: string) {
    setError('');
    try {
      const redirect = await source.startLogin(provider, returnTo);
      if (redirect.loginUrl) window.location.assign(redirect.loginUrl);
      else setError('The API returned no sign-in address for this provider. You are not signed in.');
    } catch (failure) {
      setError('Sign-in could not start (' + asApiError(failure).code + '). You are not signed in and nothing was sent to the provider.');
    }
  }

  return <main id="main" ref={main} className={styles.page} tabIndex={-1}>
    <div className={styles.column}>
      <BrandMark />
      <div className={styles.intro}>
        <IconTile icon={<ShieldCheckIcon weight="duotone" />} size="xl" tone="system" />
        <div>
          <h1 className={styles.title}>Sign in</h1>
          {/* The return target is kept for the redirect and never printed: an address can name an organization or a skill the caller has no session for. */}
          <p className={styles.lede}>Guidefold shows skills, imports and review decisions only to a confirmed member of the organization that owns them. Sign in to continue to where you were going.</p>
        </div>
      </div>
      <Card className="gap-0 py-0 ring-line-strong shadow-(--shadow-card)" render={<section aria-labelledby="login-provider-title" />}>
        <CardHeader className="border-b border-line py-(--card-spacing)">
          <CardTitle render={<h2 id="login-provider-title" />} className={styles.cardTitle}>Identity provider</CardTitle>
          <CardDescription className="font-display text-[length:var(--font-size-small)] font-medium">Session</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 py-(--card-spacing)">
          {providers.phase === 'loading' && <RouteState state="loading" title="Reading providers" description="Asking the API which identity providers are configured." />}
          {providers.phase === 'error' && providers.error && <ApiFailure error={providers.error} onRetry={providers.reload} retryLabel="Retry the provider list" />}
          {providers.phase === 'ready' && (providers.value?.providers.length
            ? <>
              <p className={styles.help}>Sign in with an account you already use. No repository scopes are requested.</p>
              {/* One primary per screen: the first configured provider carries it, the rest take
                  the system tone. All of them keep the full width and the 44 px target. */}
              {/* One primary per screen (review, important 4): the first configured provider
                  carries it, the rest take the system tone. All keep the full width and 44 px. */}
              <div className={styles.providers}>{providers.value.providers.map((provider, index) => <ActionButton key={provider.id} className={styles.provider} tone={index === 0 ? 'human' : 'system'} onClick={() => { void signIn(provider.id); }}>
                {providerIcon(provider.id)}Continue with {provider.label}
              </ActionButton>)}</div>
            </>
            : <RouteState state="empty" title="No identity provider is configured" description="This API has no identity provider, so no session can be started from this page. Nothing about your account or its organizations is shown." />)}
          {error && <Alert variant="destructive" className="border-(--signal-red) bg-graphite-900 text-stone-100 *:data-[slot=alert-description]:text-stone-100">
            <WarningCircleIcon aria-hidden="true" className="text-error-ink" />
            <AlertDescription className="text-[length:var(--font-size-small)]">{error}</AlertDescription>
          </Alert>}
        </CardContent>
      </Card>
      <p className={styles.note}>Signing in confirms who you are. It does not grant membership of any organization named in an address.</p>
    </div>
  </main>;
}
