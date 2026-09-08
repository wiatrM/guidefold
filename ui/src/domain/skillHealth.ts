/** Skill health: four gates, a recommendation and a ranking, computed from one `UsageSkill` row
 * and the open queue items for that skill. Pure functions over contract 1.1.4 fields; no new API.
 *
 * A recommendation is advice for the owner, never an action: ADR-0031 §7 forbids promoting a skill
 * from load counts, so nothing here writes anything. The owner acts through the review queue or a
 * proposal. Every floor below is a documented working threshold, not a measured one.
 */
import type {QueueItem, QueueReason, UsageSkill} from '../api/decoders';

/** Below this many exposures, reach is counted but not called high (same floor as judgments). */
export const REACH_FLOOR = 20;
/** The contract's `small_sample` floor: below this many helped-or-hindered assessments, counts only. */
export const JUDGMENT_FLOOR = 20;
/** Share of exposures that led to a verified body load for pull to count as high. */
export const PULL_HIGH_SHARE = 0.5;

/** `clear` holds; `attention` needs the owner; `low` is counted but under a floor;
 * `partial` is a lower bound; `unknown` has no data. Colour never carries this alone. */
export type GateState = 'clear' | 'attention' | 'low' | 'partial' | 'unknown';
export interface Gate { state: GateState; label: string; detail: string }
export type Recommendation = 'promote_up' | 'keep' | 'review' | 'archive_candidate';
export type SortKey = 'value' | 'pull' | 'reach';
export const sortKeys: readonly SortKey[] = ['value', 'pull', 'reach'];

export interface Funnel { exposed: number; expanded: number; loaded: number; unlinked: number; judged: number | null }

export interface SkillHealth {
  skill: UsageSkill;
  reach: Gate; pull: Gate; value: Gate; health: Gate;
  recommendation: Recommendation;
  /** The facts the recommendation was computed from, in the order they were weighed. */
  why: string[];
  funnel: Funnel;
  openItems: QueueItem[];
  /** Known shares for ranking; null when the gate is unknown. Pull keeps its lower bound. */
  pullShare: number | null; valueShare: number | null;
  /** True once helped + hindered reached the judgment floor. */
  assessed: boolean;
}

export const queueReasonLabels: Record<QueueReason, string> = {
  negative_feedback: 'Negative feedback recorded',
  source_changed: 'Source file changed since publication',
  source_removed: 'Source file absent from a complete import',
  zero_loads: 'Published but never loaded',
  missing_dependency: 'A declared dependency is missing',
};

const percent = (numerator: number, denominator: number) => Math.round((numerator / denominator) * 100) + '%';
const counts = (numerator: number, denominator: number) => numerator + ' of ' + denominator;

function reachGate(skill: UsageSkill): Gate {
  const n = skill.exposures;
  if (n === 0) return {state: 'attention', label: 'Never shown', detail: 'No card of this skill was placed into a harness context in this window.'};
  if (n < REACH_FLOOR) return {state: 'low', label: n + ' exposures', detail: 'Below the ' + REACH_FLOOR + '-exposure floor, so reach is counted but not called high.'};
  return {state: 'clear', label: n + ' exposures', detail: 'At or above the ' + REACH_FLOOR + '-exposure floor.'};
}

/** Card led to the body: `exposures_expanded / exposures`. Any unlinked load makes it a lower bound. */
function pullGate(skill: UsageSkill): Gate {
  const {exposures, exposures_expanded: expanded, loads_unlinked: unlinked} = skill;
  if (exposures === 0) return {state: 'unknown', label: 'Unknown', detail: 'Never shown, so no card could lead to a body load.'};
  if (unlinked > 0) return {state: 'partial', label: 'At least ' + counts(expanded, exposures), detail: unlinked + (unlinked === 1 ? ' verified load carries' : ' verified loads carry') + ' no search_id, so this share is a lower bound, not a fact.'};
  if (exposures < REACH_FLOOR) return {state: 'low', label: counts(expanded, exposures), detail: 'Below ' + REACH_FLOOR + ' exposures; counts only, no share.'};
  const share = expanded / exposures;
  if (share >= PULL_HIGH_SHARE) return {state: 'clear', label: counts(expanded, exposures) + ' (' + percent(expanded, exposures) + ')', detail: 'At least half of the cards led to a verified body load.'};
  return {state: 'attention', label: counts(expanded, exposures) + ' (' + percent(expanded, exposures) + ')', detail: 'Fewer than half of the cards led to a body load. A card that was not followed by a load may have sufficed or missed; only an assessment tells.'};
}

/** helped ≤ hindered on the contract's helped-over-helped-plus-hindered ratio. */
function negative(skill: UsageSkill): boolean {
  const ratio = skill.helped_ratio;
  if (!ratio || ratio.denominator === 0) return false;
  return ratio.denominator - ratio.numerator >= ratio.numerator;
}

function valueGate(skill: UsageSkill): Gate {
  const ratio = skill.helped_ratio;
  if (!ratio || ratio.denominator === 0) return {state: 'unknown', label: 'Unknown', detail: 'No helped or hindered assessment in this window; that is not 0%.'};
  const text = counts(ratio.numerator, ratio.denominator);
  if (negative(skill)) return {state: 'attention', label: ratio.small_sample ? text : text + ' (' + percent(ratio.numerator, ratio.denominator) + ')', detail: 'Hindered at least matched helped' + (ratio.small_sample ? ' on a small sample; counts only, no rate.' : '.')};
  if (ratio.small_sample) return {state: 'low', label: text, detail: 'Below ' + JUDGMENT_FLOOR + ' assessments; counts only, no rate.'};
  return {state: 'clear', label: text + ' (' + percent(ratio.numerator, ratio.denominator) + ')', detail: 'Helped over helped plus hindered, on at least ' + JUDGMENT_FLOOR + ' assessments.'};
}

function healthGate(skill: UsageSkill, openItems: QueueItem[]): Gate {
  if (openItems.length) {
    const first = queueReasonLabels[openItems[0].reason];
    const more = openItems.length - 1;
    return {state: 'attention', label: more ? first + ' +' + more + ' more' : first, detail: more
      ? 'Also open: ' + openItems.slice(1).map(item => queueReasonLabels[item.reason]).join('; ') + '. Each waits for an owner decision in Needs review.'
      : 'Open queue item waiting for an owner decision in Needs review.'};
  }
  if (skill.zero_loads) return {state: 'attention', label: 'No verified load', detail: skill.exposures > 0 ? 'Exposed but never loaded in this window.' : 'No verified load in this window; this does not prove the skill is useless.'};
  return {state: 'clear', label: 'No open item', detail: 'No drift, no open queue item, and a verified load in this window.'};
}

function hasAssessment(skill: UsageSkill): boolean {
  return (skill.feedback?.n ?? 0) > 0 || (skill.helped_ratio?.denominator ?? 0) > 0;
}

/** Order of the rules: archive candidate, review, promote up, keep. The first that matches wins. */
function recommend(skill: UsageSkill, gates: {reach: Gate; pull: Gate; value: Gate; health: Gate}, openItems: QueueItem[]): {recommendation: Recommendation; why: string[]} {
  // The four gate labels sit beside the recommendation on screen, so `why` carries only the
  // facts that decided between the rules.
  if (skill.exposures === 0 && skill.loads_verified === 0 && !hasAssessment(skill)) {
    return {recommendation: 'archive_candidate', why: ['Never shown, never loaded and never assessed in this window.']};
  }
  const reasons: string[] = openItems.map(item => 'Open queue item: ' + queueReasonLabels[item.reason]);
  if (negative(skill)) reasons.push('Hindered at least matched helped (' + counts(skill.helped_ratio!.numerator, skill.helped_ratio!.denominator) + ').');
  if (reasons.length) return {recommendation: 'review', why: reasons};
  if (gates.reach.state === 'clear' && gates.pull.state === 'clear' && gates.value.state === 'clear' && gates.health.state === 'clear') {
    return {recommendation: 'promote_up', why: ['All four gates clear on at least ' + JUDGMENT_FLOOR + ' assessments.']};
  }
  const holding = (['reach', 'pull', 'value', 'health'] as const).filter(key => gates[key].state !== 'clear');
  return {recommendation: 'keep', why: ['Not every gate is clear: ' + holding.join(', ') + '.']};
}

/** Open items only: a decided item no longer asks anything of the owner. */
export function openQueueItems(skillId: string, queue: QueueItem[]): QueueItem[] {
  return queue.filter(item => item.skill_id === skillId && !item.decision);
}

export function assessSkill(skill: UsageSkill, queue: QueueItem[]): SkillHealth {
  const openItems = openQueueItems(skill.skill_id, queue);
  const gates = {reach: reachGate(skill), pull: pullGate(skill), value: valueGate(skill), health: healthGate(skill, openItems)};
  const {recommendation, why} = recommend(skill, gates, openItems);
  const ratio = skill.helped_ratio;
  const judged = skill.feedback ? skill.feedback.n : ratio && ratio.denominator > 0 ? ratio.denominator : null;
  return {
    skill, ...gates, recommendation, why, openItems,
    funnel: {exposed: skill.exposures, expanded: skill.exposures_expanded, loaded: skill.loads_verified, unlinked: skill.loads_unlinked, judged},
    pullShare: skill.exposures > 0 ? skill.exposures_expanded / skill.exposures : null,
    valueShare: ratio && ratio.denominator > 0 ? ratio.numerator / ratio.denominator : null,
    assessed: Boolean(ratio) && ratio!.denominator >= JUDGMENT_FLOOR && !ratio!.small_sample,
  };
}

const pullRank: Record<GateState, number> = {clear: 0, attention: 0, partial: 1, low: 2, unknown: 3};

/** Sort keys, compared left to right; `skill_id` breaks every tie.
 * value: rows at the judgment floor first (by share), then small samples by how much evidence they
 * carry, then pull, then reach. A small sample never sorts above an assessed row on its percentage.
 * pull: known share on enough exposures, then lower bounds, then small counts, then unknown.
 * reach: exposures. */
function sortTuple(row: SkillHealth, key: SortKey): number[] {
  const pull = [pullRank[row.pull.state], -(row.pullShare ?? 0), -row.skill.exposures];
  if (key === 'reach') return [-row.skill.exposures];
  if (key === 'pull') return pull;
  const denominator = row.skill.helped_ratio?.denominator ?? 0;
  return row.assessed
    ? [0, -(row.valueShare ?? 0), 0, ...pull]
    : [1, -denominator, -(row.valueShare ?? 0), ...pull];
}

export function rankHealth(rows: SkillHealth[], key: SortKey = 'value'): SkillHealth[] {
  return [...rows].sort((a, b) => {
    const left = sortTuple(a, key), right = sortTuple(b, key);
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] !== right[index]) return left[index] - right[index];
    }
    return a.skill.skill_id < b.skill.skill_id ? -1 : a.skill.skill_id > b.skill.skill_id ? 1 : 0;
  });
}

export function assessSkills(skills: UsageSkill[], queue: QueueItem[], key: SortKey = 'value'): SkillHealth[] {
  return rankHealth(skills.map(skill => assessSkill(skill, queue)), key);
}

export function countRecommendations(rows: SkillHealth[]): Record<Recommendation, number> {
  const result: Record<Recommendation, number> = {promote_up: 0, keep: 0, review: 0, archive_candidate: 0};
  for (const row of rows) result[row.recommendation] += 1;
  return result;
}
