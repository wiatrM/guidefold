/** Session gate entry state, the code-entry half of email_verification_required (contract §2,
 * §4.1). `GET /api/v1/auth/callback` lands the browser here — `/login/verify-email?email=<masked>`
 * — when WorkOS answers a sign-in with email_verification_required instead of a user: the
 * gf_auth_state cookie the callback set is the only reference to the pending round trip, so this
 * page never reads or carries the pending token, the state secret, or the unmasked address
 * itself — only the masked form already in the URL.
 *
 * Like LoginRoute this renders outside the shell: no rail, no organization context, nothing read
 * from an organization the caller has not been confirmed a member of — there is no session yet.
 */
import { useEffect, useRef, useState } from 'react';
import { EnvelopeSimpleOpenIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { ActionButton, BrandMark, IconTile } from '../Shared';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { asApiError } from './apiState';
import { safeReturn } from './loginTarget';
import type { DataSource } from '../data/source';
import styles from './LoginRoute.module.css';

/** Outcomes that end the round trip: gf_auth_state no longer names a usable row, so the form is
 * replaced with a plain sentence and a way back to sign-in instead of inviting another code. */
const TERMINAL_CODES = new Set(['invalid_state', 'expired_state', 'email_code_attempts_exceeded']);

const MESSAGES: Record<string, string> = {
  invalid_request: 'Enter the code from your email.',
  email_code_invalid: "That code wasn't accepted. Check your email and try again.",
  invalid_state: 'This verification link no longer matches this browser, or was already used. Sign in again.',
  expired_state: 'This verification code has expired. Sign in again.',
  email_code_attempts_exceeded: 'Too many attempts. Sign in again.',
};

export function VerifyEmailRoute({ source, email }: { source: DataSource; email: string }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [terminal, setTerminal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const main = useRef<HTMLElement>(null);
  useEffect(() => { document.title = 'Verify your email | Guidefold'; window.scrollTo(0, 0); main.current?.focus(); }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting || terminal) return;
    const value = code.trim();
    if (!value) { setError(MESSAGES.invalid_request); return; }
    setSubmitting(true);
    setError('');
    try {
      const result = await source.verifyEmailCode(value, 'verify-email:' + Date.now());
      window.location.assign(safeReturn(result.returnTo));
    } catch (failure) {
      const apiCode = asApiError(failure).code;
      setError(MESSAGES[apiCode] ?? 'The code could not be verified. Sign in again.');
      setTerminal(TERMINAL_CODES.has(apiCode) || !(apiCode in MESSAGES));
      // A wrong code (email_code_invalid) leaves the field for a fresh attempt; a terminal
      // outcome never resubmits, so what remains in the field does not matter either way.
      if (!TERMINAL_CODES.has(apiCode) && apiCode in MESSAGES) setCode('');
    } finally {
      setSubmitting(false);
    }
  }

  return <main id="main" ref={main} className={styles.page} tabIndex={-1}>
    <div className={styles.column}>
      <BrandMark />
      <div className={styles.intro}>
        <IconTile icon={<EnvelopeSimpleOpenIcon weight="duotone" />} size="xl" tone="system" />
        <div>
          <h1 className={styles.title}>Check your email</h1>
          <p className={styles.lede}>WorkOS sent a one-time code to {email || 'your email address'}. Enter it to finish signing in.</p>
        </div>
      </div>
      <Card className="gap-0 py-0 ring-line-strong shadow-(--shadow-card)" render={<section aria-labelledby="verify-email-title" />}>
        <CardHeader className="border-b border-line py-(--card-spacing)">
          <CardTitle render={<h2 id="verify-email-title" />} className={styles.cardTitle}>Verification code</CardTitle>
          <CardDescription className="font-display text-[length:var(--font-size-small)] font-medium">Sign-in</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 py-(--card-spacing)">
          {!terminal && <form onSubmit={submit} className="grid gap-3" noValidate>
            <div className="grid gap-1.5">
              <Label htmlFor="verify-email-code">Code from your email</Label>
              <Input id="verify-email-code" name="code" inputMode="numeric" autoComplete="one-time-code" autoFocus
                value={code} onChange={event => setCode(event.target.value)} disabled={submitting}
                aria-invalid={error ? true : undefined} aria-describedby={error ? 'verify-email-error' : undefined} />
            </div>
            <ActionButton type="submit" tone="human" className={styles.provider} disabled={submitting || !code.trim()}>
              {submitting ? 'Verifying…' : 'Verify and continue'}
            </ActionButton>
          </form>}
          {terminal && <ActionButton href="/login" tone="system" className={styles.provider}>Back to sign in</ActionButton>}
          {error && <Alert id="verify-email-error" variant="destructive" className="border-(--signal-red) bg-graphite-900 text-stone-100 *:data-[slot=alert-description]:text-stone-100">
            <WarningCircleIcon aria-hidden="true" className="text-error-ink" />
            <AlertDescription className="text-[length:var(--font-size-small)]">{error}</AlertDescription>
          </Alert>}
        </CardContent>
      </Card>
      <p className={styles.note}>WorkOS does not offer a way to resend this code from here; sign in again to get a new one.</p>
    </div>
  </main>;
}
