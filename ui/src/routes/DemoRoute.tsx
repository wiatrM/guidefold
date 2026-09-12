import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle, FileCode, Sparkle } from '@phosphor-icons/react';
import { ActionButton, MetricRow, Panel, StateBadge } from '../Shared';
import styles from './OnboardingRoutes.module.css';

/** C26: a self-contained sample repo. It never calls the API or mixes demo data with an org. */
export function DemoRoute() {
  return <div className={styles.route}>
    <Panel title="See the first value" eyebrow="Guided demo · sample repository" icon={<Sparkle weight="regular" aria-hidden="true" />}>
      <p>This is a fictional checkout. Nothing here is your organization, and no sample result is recorded as customer evidence.</p>
      <MetricRow items={[
        { label: 'Sample instructions', value: '3', detail: 'auth, API and migrations' },
        { label: 'Suggested next step', value: '1', detail: 'one concrete procedure' },
        { label: 'Customer data read', value: '0', detail: 'the demo is isolated' },
      ]} />
    </Panel>
    <Panel title="Choose a procedure" eyebrow="Sample result" icon={<FileCode weight="regular" aria-hidden="true" />}>
      <ul className={styles.stack}>
        <li><strong>Adding an authenticated endpoint</strong><span className={styles.linkHint}>Requires the company auth middleware and request test.</span><StateBadge tone="system">ready to inspect</StateBadge></li>
        <li><strong>Rotating a service credential</strong><span className={styles.linkHint}>Shows a safe prerequisite and rollback step.</span><StateBadge tone="neutral">sample</StateBadge></li>
        <li><strong>Running a database migration</strong><span className={styles.linkHint}>Highlights owner review before publication.</span><StateBadge tone="neutral">sample</StateBadge></li>
      </ul>
      <div className={styles.notice} role="status"><CheckCircle weight="regular" aria-hidden="true" /><p>The demo stops before login, import or publication. Use your own organization to measure a real task.</p></div>
      <ActionButton href="/import?step=login" tone="human">Use your own repository<ArrowRight weight="regular" aria-hidden="true" /></ActionButton>
    </Panel>
    <p className={styles.help}><Link to="/import?step=login">Sign in</Link> when you are ready. Demo content is never copied into an organization.</p>
  </div>;
}
