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
import { useEffect, useState } from 'react';
import { ShieldCheck, GithubLogo, GoogleLogo, SignIn } from '@phosphor-icons/react';
import { ActionButton, BrandMark, Panel, RouteState } from '../Shared';
import { ApiFailure, asApiError, useAsync } from './apiState';
import type { DataSource } from '../data/source';
import styles from './LoginRoute.module.css';

export {DEFAULT_RETURN, loginHref, safeReturn} from './loginTarget';

const providerIcon = (id: string) => id === 'github'
  ? <GithubLogo weight="regular" aria-hidden="true" />
  : id === 'google' ? <GoogleLogo weight="regular" aria-hidden="true" /> : <SignIn weight="regular" aria-hidden="true" />;

export function LoginRoute({ source, returnTo }: { source: DataSource; returnTo: string }) {
  const providers = useAsync(() => source.getAuthProviders(), 'auth-providers');
  const [error, setError] = useState('');
  useEffect(() => { document.title = 'Sign in | Guidefold'; }, []);

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

  return <main id="main" className={styles.page} tabIndex={-1}>
    <div className={styles.column}>
      <BrandMark />
      <h1 className={styles.title}>Sign in</h1>
      {/* The requested address is kept, never printed: it can carry an organization slug, a
          repository and a skill URN, and an address is not content this page may echo back on an
          unauthenticated screen (UX 7, the same rule the error states follow). */}
      <p className={styles.lede}>Guidefold shows skills, imports and review decisions only to a confirmed member of the organization that owns them. Sign in to continue where you were going.</p>
      <Panel title="Identity provider" eyebrow="Session" icon={<ShieldCheck weight="regular" aria-hidden="true" />}>
        {providers.phase === 'loading' && <RouteState state="loading" title="Reading providers" description="Asking the API which identity providers are configured." />}
        {providers.phase === 'error' && providers.error && <ApiFailure error={providers.error} onRetry={providers.reload} retryLabel="Retry the provider list" />}
        {providers.phase === 'ready' && (providers.value?.providers.length
          ? <>
            <p className={styles.help}>Sign in with an account you already use. No repository scopes are requested.</p>
            <div className={styles.providers}>{providers.value.providers.map(provider => <ActionButton key={provider.id} className={styles.provider} tone="human" onClick={() => { void signIn(provider.id); }}>
              {providerIcon(provider.id)}Continue with {provider.label}
            </ActionButton>)}</div>
          </>
          : <RouteState state="empty" title="No identity provider is configured" description="This API has no identity provider, so no session can be started from this page. Nothing about your account or its organizations is shown." />)}
        {error && <p className={styles.error} role="alert">{error}</p>}
      </Panel>
      <p className={styles.note}>Signing in confirms who you are. It does not grant membership of any organization named in an address.</p>
    </div>
  </main>;
}
