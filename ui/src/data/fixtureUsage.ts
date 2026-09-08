/** Simulated usage ledger for the Meridian fixture: six skills whose counts land on every gate state
 * and every recommendation of `domain/skillHealth`. Nothing here comes from an adapter; the fixture
 * repository has no real events (04-wireframes §6), and every screen that shows these rows says so.
 * Totals are the sums of the rows so the funnel and the per-skill table agree.
 */
import type {Usage, UsageSkill} from '../api/decoders';

const row = (over: Partial<UsageSkill> & {skill_id: string; scope: string; owner: string}): UsageSkill => ({
  revision: null, card_revision: null, content_sha256: null, harness: 'claude',
  exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0,
  use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0,
  feedback: null, helped_ratio: null, zero_loads: false,
  ...over,
});

export const fixtureUsageSkills: UsageSkill[] = [
  // Promote up: reach, pull, value and health all clear on 30 assessments.
  row({skill_id: 'urn:skill:meridian:_root:postgres-production', scope: '_root', owner: 'platform-engineering', revision: 'fixture-rev-postgres',
    exposures: 84, exposures_expanded: 51, loads_verified: 51, context_loaded: 47, context_unknown: 4,
    use_reported: 22, use_observed: 19, use_episodes: 33,
    feedback: {helped: 26, hindered: 4, mixed: 3, not_applicable: 0, unknown: 0, n: 33},
    helped_ratio: {numerator: 26, denominator: 30, small_sample: false}}),
  // Keep: value clear, but five unlinked loads make pull a lower bound.
  row({skill_id: 'urn:skill:meridian:_root:release-process', scope: '_root', owner: 'platform-engineering', revision: 'fixture-rev-release',
    exposures: 40, exposures_expanded: 9, loads_verified: 14, loads_unlinked: 5, context_loaded: 12, context_unknown: 2,
    use_reported: 12, use_observed: 10, use_episodes: 22,
    feedback: {helped: 15, hindered: 7, mixed: 0, not_applicable: 0, unknown: 0, n: 22},
    helped_ratio: {numerator: 15, denominator: 22, small_sample: false}}),
  // Review: a source_changed item is open and the ledger holds 28 assessments in its favour.
  row({skill_id: 'urn:skill:meridian:atlas.identity:rbac-policies', scope: 'atlas.identity', owner: 'identity-team', revision: 'fixture-rev-rbac',
    exposures: 55, exposures_expanded: 30, loads_verified: 30, context_loaded: 30,
    use_reported: 16, use_observed: 16, use_episodes: 28,
    feedback: {helped: 24, hindered: 4, mixed: 0, not_applicable: 0, unknown: 0, n: 28},
    helped_ratio: {numerator: 24, denominator: 28, small_sample: false}}),
  // Review: hindered outnumbers helped on a small sample; the computed negative_feedback item is open.
  row({skill_id: 'urn:skill:meridian:forge.ontology:object-type-migrations', scope: 'forge.ontology', owner: 'ontology-team', revision: 'fixture-rev-migrations',
    exposures: 31, exposures_expanded: 20, loads_verified: 20, context_loaded: 18, context_unknown: 2,
    use_reported: 9, use_observed: 8, use_episodes: 12,
    feedback: {helped: 5, hindered: 7, mixed: 0, not_applicable: 0, unknown: 0, n: 12},
    helped_ratio: {numerator: 5, denominator: 12, small_sample: true}}),
  // Keep: every gate is under a floor (12 exposures, 4 assessments), nothing is wrong.
  row({skill_id: 'urn:skill:meridian:_root:monorepo-conventions', scope: '_root', owner: 'platform-engineering', revision: 'fixture-rev-conventions',
    exposures: 12, exposures_expanded: 7, loads_verified: 7, context_loaded: 7,
    use_reported: 4, use_observed: 4, use_episodes: 4,
    feedback: {helped: 3, hindered: 1, mixed: 0, not_applicable: 0, unknown: 0, n: 4},
    helped_ratio: {numerator: 3, denominator: 4, small_sample: true}}),
  // Archive candidate: published, never shown, never loaded, never assessed.
  row({skill_id: 'urn:skill:meridian:_root:adr-process', scope: '_root', owner: 'platform-engineering', revision: 'fixture-rev-adr', zero_loads: true}),
];

export const fixtureUsage: Usage = {
  window: {from: '2026-08-09T00:00:00Z', to: '2026-09-08T00:00:00Z', watermark: '2026-09-08T06:00:00Z'},
  coverage: {events_received: 1437, dropped_reported: 0, oldest_lag_s: 12, task_ids_present: true},
  totals: {
    exposures: 222, loads_verified: 122, context_loaded: 114, context_unknown: 8,
    use_reported: 63, use_observed: 57, use_episodes: 99, exposures_expanded: 117, loads_unlinked: 5,
    feedback: {helped: 73, hindered: 23, mixed: 3, not_applicable: 0, unknown: 0, n: 99},
  },
  skills: fixtureUsageSkills,
  queue: [
    {item_id: 'fixture-queue-rbac', skill_id: 'urn:skill:meridian:atlas.identity:rbac-policies', revision: 'fixture-rev-rbac', reason: 'source_changed', since: '2026-09-02T10:15:00Z', evidence: {commit: '88e40456', path: 'platforms/atlas/identity/rbac-policies/SKILL.md'}, decision: null},
    {item_id: 'negative_feedback:urn:skill:meridian:forge.ontology:object-type-migrations:fixture-rev-migrations', skill_id: 'urn:skill:meridian:forge.ontology:object-type-migrations', revision: 'fixture-rev-migrations', reason: 'negative_feedback', since: '2026-08-28T08:00:00Z', evidence: {hindered: 7, helped: 5}, decision: null},
    {item_id: 'zero_loads:urn:skill:meridian:_root:adr-process:fixture-rev-adr', skill_id: 'urn:skill:meridian:_root:adr-process', revision: 'fixture-rev-adr', reason: 'zero_loads', since: '2026-08-16T00:00:00Z', evidence: {exposures: 0, loads: 0, days_since_publication: 23}, decision: null},
  ],
  health: {adapters: [{harness: 'claude', adapter_version: '0.4.1', capabilities: ['search', 'use'], last_seen_at: '2026-09-08T05:58:00Z', lag_s: 12, dropped: 0}]},
};
