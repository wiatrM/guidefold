/** The one repository selector of the console (ADR-0047, contract §4.10).
 *
 * The organisation is the default read scope; picking a repository narrows every view that reads
 * the catalogue, proposals or telemetry, and the choice travels in `?repo=` so a link keeps it.
 * "All repositories" means what the API says it means: every repository this principal may read,
 * never a client-side sum.
 *
 * A native `<select>`, deliberately: the shadcn `Select` is a Base UI floating part and jsdom
 * hangs on those in this suite (docs/reports/ui/console-shadcn-20260912.md), and a form control
 * that changes the address on every keystroke of arrow navigation would be a worse control
 * anyway. Styled from tokens.css like the Library filters, so it reads as one family.
 */
import {Label} from '@/components/ui/label';
import type {Repo} from '../../api/decoders';
import css from './RepositoryFilter.module.css';

export const ALL_REPOSITORIES = '';

export function RepositoryFilter({id = 'repository-filter', repos, value, onChange, disabled = false}: {
  id?: string;
  /** Null while the list has not arrived or could not be read; the current value still renders. */
  repos: Repo[] | null;
  /** The repository in the address, or null for the whole organisation. */
  value: string | null;
  onChange: (repo: string | null) => void;
  disabled?: boolean;
}) {
  const known = repos ?? [];
  // The address may name a repository the list does not (a stale link, a repository created
  // elsewhere): keep it selectable so the selection is visible, never silently reset to "All".
  const extra = value && !known.some(repo => repo.repo_id === value) ? [value] : [];
  return <div className={css.filter} data-slot="repository-filter">
    <Label htmlFor={id} className={css.label}>Repository</Label>
    <select id={id} className={css.select} value={value ?? ALL_REPOSITORIES} disabled={disabled}
      onChange={event => onChange(event.currentTarget.value === ALL_REPOSITORIES ? null : event.currentTarget.value)}>
      <option value={ALL_REPOSITORIES}>All repositories</option>
      {known.map(repo => <option key={repo.repo_id} value={repo.repo_id}>{repo.repo_id}</option>)}
      {extra.map(repo => <option key={repo} value={repo}>{repo}</option>)}
    </select>
    {repos === null && <small className={css.note}>Repository list not available yet.</small>}
  </div>;
}
