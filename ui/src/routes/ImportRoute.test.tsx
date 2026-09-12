import { describe, expect, test, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ApiImportRoute } from './OnboardingRoutes';
import { ApiError } from '../api/client';
import type { ImportPlan, ImportStatus } from '../api/decoders';
import type { ApiRouteContext } from '../domain';
import type { DataSource } from '../data/source';
import { fakeSource } from '../test/fakes';

const me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' as const }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};

const status = (over: Partial<ImportStatus> = {}): ImportStatus => ({
  import_id: 'im-1', state: 'ready', manifest_digest: 'digest-1', commit: 'c0ffee', complete: true,
  counts: { files: 3, accepted: 2, omitted: 1, failed: 0, new_blobs: 1, reused_blobs: 2, skills: 2, documents: 0 },
  files: [
    { path: 'a/SKILL.md', sha256: 's1', size: 10, kind: 'skill', status: 'accepted', reason: null, skill_id: 'urn:a' },
    { path: '.env', sha256: null, size: null, kind: null, status: 'omitted', reason: 'secret_pattern', skill_id: null },
  ],
  files_truncated: false,
  jobs: [{ job_id: 'j1', kind: 'import.parse', state: 'done', attempts: 1, generation: 2, error: null, cost: null, started_at: null, finished_at: null }],
  publication: { snapshot_id: 'sn-1', state: 'published', error: null },
  created_at: '2026-09-06T10:00:00Z', updated_at: '2026-09-06T10:00:05Z',
  ...over,
});

function renderRoute(source: DataSource, search = '', over: Partial<ApiRouteContext> = {}) {
  const params = new URLSearchParams(search);
  const ctx: ApiRouteContext = {
    source, access: { status: 'confirmed', me, checkedAt: 1 }, me, org: 'meridian', repo: 'monorepo',
    role: 'owner', params, view: 'import',
    href: (view, changes = {}) => '/' + view + '?' + new URLSearchParams(Object.entries(changes).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => [key, String(value)])).toString(),
    go: vi.fn(),
    ...over,
  };
  return render(<MemoryRouter><ApiImportRoute ctx={ctx} /></MemoryRouter>);
}

describe('Import route, hosted API, six states', () => {
  test('Empty: no repository selected sends the operator back to the repository step', async () => {
    renderRoute(fakeSource({ listRepos: async () => [] }), 'step=result', { repo: null });
    expect(await screen.findByText('No repository selected')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Choose a repository' })).toBeInTheDocument();
  });

  test('Loading: the import list is awaited before anything is claimed', async () => {
    renderRoute(fakeSource({ listImports: () => new Promise(() => {}) }), 'step=result');
    expect(await screen.findByText('Reading imports')).toBeInTheDocument();
  });

  test('Partial: accepted, omitted and failed files are separated', async () => {
    const source = fakeSource({
      listImports: async () => [status({ state: 'partial' })],
      getImport: async () => status({ state: 'partial', counts: { files: 3, accepted: 2, omitted: 1, failed: 1, new_blobs: 0, reused_blobs: 0, skills: 2, documents: 0 } }),
    });
    renderRoute(source, 'step=result&import_id=im-1');
    expect(await screen.findByText('Partial')).toBeInTheDocument();
    expect(screen.getByText('Accepted files (1)')).toBeInTheDocument();
    expect(screen.getByText('Omitted files (1)')).toBeInTheDocument();
    expect(screen.getByText('Failed files (0)')).toBeInTheDocument();
    expect(screen.getByText('secret_pattern')).toBeInTheDocument();
  });

  test('Partial: a truncated file list is named, never read as the whole import', async () => {
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status({
        counts: { files: 24000, accepted: 23999, omitted: 1, failed: 0, new_blobs: 1, reused_blobs: 2, skills: 2, documents: 0 },
        files_truncated: true,
      }),
    });
    renderRoute(source, 'step=result&import_id=im-1');
    expect(await screen.findByText(/The API returned a shortened file list: 2 of 24000 files are shown below/)).toBeInTheDocument();
    // The metric row keeps the import's own count; only the list below is short.
    expect(screen.getByText('23999')).toBeInTheDocument();
  });

  test('Error: retry re-reads the same import_id', async () => {
    const asked: string[] = [];
    let fail = true;
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async (_target, importId: string) => {
        asked.push(importId);
        if (fail) throw new ApiError({ status: 503, code: 'unavailable', message: 'no' });
        return status();
      },
    });
    renderRoute(source, 'step=result&import_id=im-1');
    const retry = await screen.findByRole('button', { name: 'Retry this import status' });
    fail = false;
    await userEvent.click(retry);
    await waitFor(() => expect(asked).toEqual(['im-1', 'im-1']));
  });

  test('Degraded: a failed publication is reported next to the readable files', async () => {
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status({ publication: { snapshot_id: null, state: 'failed', error: 'missing_required_resource' } }),
    });
    renderRoute(source, 'step=result&import_id=im-1');
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
    expect(screen.getByText(/the publication step failed/)).toBeInTheDocument();
  });

  test('Restricted: a denial says nothing about the content', async () => {
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => { throw new ApiError({ status: 403, code: 'forbidden', message: 'forbidden' }); },
    });
    renderRoute(source, 'step=result&import_id=im-1');
    expect(await screen.findByText('Not available to your account')).toBeInTheDocument();
    expect(screen.queryByText('a/SKILL.md')).not.toBeInTheDocument();
  });
});

describe('Import route, sign in and context', () => {
  test('the wizard has no sign-in step: a stale ?step=login falls through to the first real one', async () => {
    const source = fakeSource({ listImports: async () => [] });
    renderRoute(source, 'step=login');
    // Sign-in moved to the full-width /login page (app.tsx gate); an unauthenticated request
    // never reaches this route, so a bookmarked step is just an unknown step here, and the
    // route resolves the same first real step it would have picked with no step at all.
    expect(await screen.findByText('No import yet')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Continue with GitHub/ })).not.toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Import progress' })).queryByText('Sign in')).not.toBeInTheDocument();
  });

  test('the CLI block names the real organization, never a fixture', async () => {
    const source = fakeSource({ listRepos: async () => [{ repo_id: 'monorepo', name: null, git_host_url: null, created_at: null, created: false }] });
    renderRoute(source, 'step=preview');
    expect(await screen.findByText(/guidefold org use meridian/)).toBeInTheDocument();
    expect(screen.queryByText(/Local simulation/)).not.toBeInTheDocument();
  });

  test('the browser package path hashes selected files, uploads missing blobs and finalizes once', async () => {
    // jsdom does not expose SubtleCrypto, while the hosted browser path uses the
    // Web Crypto API in real browsers. Keep this contract test on the same API.
    vi.stubGlobal('crypto', webcrypto);
    try {
    const createImport = vi.fn(async (_target: unknown, manifest: any) => ({ import_id: 'browser-import', state: 'created' as const, missing_blobs: [manifest.files[0].sha256], limits: null, reused_import_id: null }));
    const uploadImportBlob = vi.fn(async () => {});
    const finalizeImport = vi.fn(async () => status({ import_id: 'browser-import', state: 'queued' }));
    const go = vi.fn();
    const source = fakeSource({ listRepos: async () => [], createImport, uploadImportBlob, finalizeImport });
    renderRoute(source, 'step=preview', { go });
    const input = await screen.findByLabelText('Files');
    const file = new File(['# Auth\n'], 'SKILL.md', { type: 'text/markdown' });
    Object.defineProperty(file, 'arrayBuffer', { value: async () => new TextEncoder().encode('# Auth\n').buffer });
    await userEvent.upload(input, file);
    expect(await screen.findByText('1 file(s) selected.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Import selected files' }));
    await waitFor(() => expect(createImport).toHaveBeenCalledTimes(1));
    expect(uploadImportBlob).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'browser-import', expect.stringMatching(/^[0-9a-f]{64}$/), expect.any(Uint8Array));
    expect(finalizeImport).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'browser-import', 'browser-finalize:browser-import');
    expect(go).toHaveBeenCalledWith('import', { step: 'result', import_id: 'browser-import' });
    } finally {
      vi.unstubAllGlobals();
    }
  });

  test('an owner can register a repository before using the browser package path', async () => {
    const createRepo = vi.fn(async () => ({ repo_id: 'local-repo', name: null, git_host_url: null, created_at: null, created: true }));
    const go = vi.fn();
    renderRoute(fakeSource({ listRepos: async () => [], createRepo }), 'step=preview', { repo: null, go });
    await userEvent.type(await screen.findByLabelText('Repository id'), 'local-repo');
    await userEvent.click(screen.getByRole('button', { name: 'Register repository' }));
    await waitFor(() => expect(createRepo).toHaveBeenCalledWith('meridian', { repo_id: 'local-repo', git_host_url: null }, 'create-repo:meridian:local-repo'));
    expect(go).toHaveBeenCalledWith('import', { repo: 'local-repo', step: 'result' });
  });

  test('the browser package path rejects obvious secret files before upload', async () => {
    const createImport = vi.fn();
    renderRoute(fakeSource({ listRepos: async () => [], createImport }), 'step=preview');
    const input = await screen.findByLabelText('Files');
    const file = new File(['TOKEN=secret\n'], '.env', { type: 'text/plain' });
    Object.defineProperty(file, 'arrayBuffer', { value: async () => new TextEncoder().encode('TOKEN=secret\n').buffer });
    await userEvent.upload(input, file);
    await userEvent.click(screen.getByRole('button', { name: 'Import selected files' }));
    expect(await screen.findByText('sensitive file rejected: .env')).toBeInTheDocument();
    expect(createImport).not.toHaveBeenCalled();
  });

  test('a member sees the read-only notice and no repository form', async () => {
    const source = fakeSource({ listRepos: async () => [] });
    renderRoute(source, 'step=preview', { role: 'member' });
    expect(await screen.findByText('Member access is read only here. Import and organization changes require an owner.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Repository id')).not.toBeInTheDocument();
  });

  test('an owner can grant repository access and assign a reviewer', async () => {
    const setRepoAccess = vi.fn(async () => ({ user_id: 'u2', email: 'dev@example.com', name: 'Dev', access: 'write' as const, created_at: null }));
    const assignReviewer = vi.fn(async () => {});
    const source = fakeSource({
      listRepos: async () => [{ repo_id: 'monorepo', name: null, git_host_url: null, created_at: null, created: false }],
      listMembers: async () => [{ user_id: 'u2', email: 'dev@example.com', name: 'Dev', role: 'member' as const, joined_at: null }],
      listRepoAccess: async () => [], listReviewers: async () => [], setRepoAccess, assignReviewer,
    });
    renderRoute(source, 'step=preview');
    await userEvent.selectOptions(await screen.findByLabelText('Member'), 'u2');
    await userEvent.selectOptions(screen.getByLabelText('Access level'), 'write');
    await userEvent.click(screen.getByRole('button', { name: 'Save repository access' }));
    await waitFor(() => expect(setRepoAccess).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'u2', 'write', expect.stringContaining('repo-access:')));
    await userEvent.selectOptions(screen.getByLabelText('Reviewer'), 'u2');
    await userEvent.click(screen.getByRole('button', { name: 'Assign reviewer' }));
    await waitFor(() => expect(assignReviewer).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'u2', expect.stringContaining('repo-reviewer:')));
  });

  test('polling stops on a terminal state and is cancelled on unmount', async () => {
    vi.useFakeTimers();
    try {
      const getImport = vi.fn(async () => status({ state: 'parsing' }));
      const view = renderRoute(fakeSource({ listImports: async () => [status()], getImport }), 'step=result&import_id=im-1');
      await vi.waitFor(() => expect(getImport).toHaveBeenCalledTimes(1));
      await vi.advanceTimersByTimeAsync(2000);
      expect(getImport).toHaveBeenCalledTimes(2);
      view.unmount();
      await vi.advanceTimersByTimeAsync(6000);
      expect(getImport).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });
});

const plan = (over: Partial<ImportPlan> = {}): ImportPlan => ({
  groups: [{ group_id: 'g1', kind: 'extraction', scope: 'atlas.identity', owner: 'identity-team', inputs: ['a/SKILL.md'], n_inputs: 1, estimated_tokens: 500, estimated_calls: 1 }],
  limits: { max_files: 20, max_bytes: 1048576, max_groups: 5, max_proposals_per_group: 5, max_neighbours: 10, max_tokens: 1000, max_calls: 10, max_usd: 5 },
  estimated_usd_max: 1.5,
  estimated_calls: 1,
  groups_skipped: {},
  generator: { name: 'openai', configured: true, generator: 'openai', version: 'v3', model: 'gpt-x' },
  ...over,
});

describe('Import route, proposal generation panel', () => {
  test('the plan is read and shown before any generation starts', async () => {
    const getImportPlan = vi.fn(async () => plan());
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status(),
      getImportPlan,
    });
    renderRoute(source, 'step=result&import_id=im-1');
    expect(await screen.findByText('Groups and inputs (1)')).toBeInTheDocument();
    expect(getImportPlan).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'im-1', ['extraction', 'enrichment', 'consolidation']);
    expect(screen.getByText('Fixed by the API: at most 5 groups, 5 proposals per group, 10 neighbours.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate proposals' })).toBeInTheDocument();
  });

  test('a plan whose groups were cut by max_groups says so instead of listing a short plan', async () => {
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status(),
      getImportPlan: async () => plan({ groups_skipped: { extraction: 3, enrichment: 0, consolidation: 1 } }),
    });
    renderRoute(source, 'step=result&import_id=im-1');
    expect(await screen.findByText(/The plan limit of 5 groups left out 4 scope\(s\): 3 extraction, 1 consolidation/)).toBeInTheDocument();
  });

  test('a plan that covers every scope carries no partial notice', async () => {
    const source = fakeSource({ listImports: async () => [status()], getImport: async () => status(), getImportPlan: async () => plan() });
    renderRoute(source, 'step=result&import_id=im-1');
    await screen.findByText('Groups and inputs (1)');
    expect(screen.queryByText(/left out/)).not.toBeInTheDocument();
  });

  test('a member sees the owner note instead of the plan; the plan is never read', async () => {
    const getImportPlan = vi.fn();
    const source = fakeSource({ listImports: async () => [status()], getImport: async () => status(), getImportPlan });
    renderRoute(source, 'step=result&import_id=im-1', { role: 'member' });
    expect(await screen.findByText('Generate proposals')).toBeInTheDocument();
    expect(getImportPlan).not.toHaveBeenCalled();
  });

  test('a limit above the plan ceiling is rejected before any request is sent', async () => {
    const generateProposals = vi.fn();
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status(),
      getImportPlan: async () => plan(),
      generateProposals,
    });
    renderRoute(source, 'step=result&import_id=im-1');
    await screen.findByText('Groups and inputs (1)');
    await userEvent.type(screen.getByLabelText('Max tokens'), '5000');
    await userEvent.click(screen.getByRole('button', { name: 'Generate proposals' }));
    expect(await screen.findByText('Max tokens cannot exceed the plan estimate of 1000.')).toBeInTheDocument();
    expect(generateProposals).not.toHaveBeenCalled();
  });

  test('a negative limit is rejected as invalid', async () => {
    const generateProposals = vi.fn();
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status(),
      getImportPlan: async () => plan(),
      generateProposals,
    });
    renderRoute(source, 'step=result&import_id=im-1');
    await screen.findByText('Groups and inputs (1)');
    await userEvent.type(screen.getByLabelText('Max model calls'), '-1');
    await userEvent.click(screen.getByRole('button', { name: 'Generate proposals' }));
    expect(await screen.findByText('Max model calls must be a non-negative number.')).toBeInTheDocument();
    expect(generateProposals).not.toHaveBeenCalled();
  });

  test('generate opens one job per kind; a job skipped for llm_not_configured is shown as honest, not an error', async () => {
    let generated = false;
    const generateProposals = vi.fn(async () => {
      generated = true;
      return { job_ids: ['j-gen-1'], plan: plan({ generator: { name: 'none', configured: false, generator: 'none', version: '', model: null } }) };
    });
    const source = fakeSource({
      listImports: async () => [status()],
      getImport: async () => status({
        jobs: generated
          ? [status().jobs[0], { job_id: 'j-gen-1', kind: 'proposal.generate', state: 'skipped', attempts: 1, generation: 1, error: 'llm_not_configured', cost: null, started_at: null, finished_at: null }]
          : [status().jobs[0]],
      }),
      getImportPlan: async () => plan({ generator: { name: 'none', configured: false, generator: 'none', version: '', model: null } }),
      generateProposals,
    });
    renderRoute(source, 'step=result&import_id=im-1');
    const button = await screen.findByRole('button', { name: 'Generate proposals' });
    expect(screen.getByText('No generator configured')).toBeInTheDocument();
    await userEvent.click(button);
    await waitFor(() => expect(generateProposals).toHaveBeenCalledTimes(1));
    expect(generateProposals).toHaveBeenCalledWith(
      { org: 'meridian', repo: 'monorepo' }, 'im-1',
      { kinds: ['extraction', 'enrichment', 'consolidation'], limits: {} },
      expect.any(String),
    );
    expect(await screen.findByText('j-gen-1')).toBeInTheDocument();
    expect(await screen.findByText('skipped')).toBeInTheDocument();
    expect(screen.getByText(/No generator is configured on this API\. This is not a failure/)).toBeInTheDocument();
  });
});

describe('Import route, stepper', () => {
  const providers = fakeSource({ getAuthProviders: async () => ({ mode: 'dev' as const, providers: [{ id: 'github', label: 'GitHub', login_url: '/api/v1/auth/login/github' }] }) });

  test('the three steps are numbered and named for the hosted flow; the current one carries aria-current', () => {
    renderRoute(fakeSource({ listImports: async () => [] }), 'step=result');
    const list = screen.getByRole('list', { name: 'Import progress' });
    const items = within(list).getAllByRole('listitem');
    // Sign-in is not among them: it is the /login page the shell redirects to, not a step.
    expect(items.map(item => within(item).getByText(/^(Organization|Repository|Import status)$/).textContent)).toEqual(['Organization', 'Repository', 'Import status']);
    expect(items[2]).toHaveAttribute('aria-current', 'step');
    expect(items[0]).not.toHaveAttribute('aria-current');
    expect(within(items[0]).getByText('01')).toBeInTheDocument();
  });

  test('the wizard never starts a sign-in of its own', async () => {
    renderRoute(providers, '', { org: null, repo: null, role: null });
    const list = screen.getByRole('list', { name: 'Import progress' });
    expect(within(list).getAllByRole('listitem')[0]).toHaveAttribute('aria-current', 'step');
    expect(await screen.findByText('Your organizations')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Continue with GitHub/ })).not.toBeInTheDocument();
  });

  test('a signed-in operator without an organisation lands on the organisation step', async () => {
    renderRoute(fakeSource({ listOrgs: async () => [] }), '', { org: null, repo: null, role: null });
    expect(await screen.findByText('No organization yet')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Import progress' }).querySelectorAll('[aria-current="step"]')).toHaveLength(1);
    expect(screen.getByRole('button', { name: /Create organization/ })).toBeInTheDocument();
  });

  test('the repository step lists repositories with a Git host or Unknown and the CLI commands for this organisation', async () => {
    renderRoute(fakeSource({ listRepos: async () => [
      { repo_id: 'monorepo', name: null, git_host_url: 'https://github.example.test/meridian/monorepo', created_at: null, created: false },
      { repo_id: 'docs', name: null, git_host_url: null, created_at: null, created: false },
    ] }), 'step=preview');
    expect(await screen.findByText('https://github.example.test/meridian/monorepo')).toBeInTheDocument();
    const docs = screen.getByText('docs').closest('tr')!;
    expect(within(docs).getByText('Unknown')).toBeInTheDocument();
    expect(screen.getByText(/guidefold org use meridian/)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Open import status' })).toHaveLength(2);
  });

  test('the result step lists imports newest first with a state badge and a link that keeps the import id in the address', async () => {
    renderRoute(fakeSource({
      listImports: async () => [status({ import_id: 'im-2', state: 'partial' }), status({ import_id: 'im-1' })],
      getImport: async () => status({ import_id: 'im-2', state: 'partial' }),
    }), 'step=result&import_id=im-2');
    const rows = within(await screen.findByRole('table', { name: 'Imports for this repository' })).getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('im-2');
    expect(within(rows[0]).getByText('partial')).toBeInTheDocument();
    expect(within(rows[1]).getByRole('link', { name: 'Read this import' })).toHaveAttribute('href', expect.stringContaining('import_id=im-1'));
  });
});
