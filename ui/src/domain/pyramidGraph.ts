import type {RelationEdge, SkillSummary} from '../api/decoders';
import {knowledgeLayerOrder, type PyramidLayer} from './pyramid';

export interface PyramidGraphNode {id: string; label: string; detail: string}
export interface PyramidGraphBand {layer: PyramidLayer; items: PyramidGraphNode[]}
export interface PyramidGraphEdge {from: string; to: string}

const layerOf = (skill: SkillSummary): PyramidLayer => skill.knowledge_layer ?? 'unclassified';

/** API-mode counterpart of `pyramid.ts`'s fixture-only `pyramidBands`: kept as its own small
 * function rather than a shared generic, since the two sources disagree on field names
 * (`Skill.refines` denormalised on each skill vs a separately fetched edge list) and sharing one
 * generic here would buy indirection, not less code, for two call sites
 * (`dry-without-wrong-abstraction`). Groups `skills` — already filtered to one repository scope
 * by the caller (`listSkills({scope})`) — into all four knowledge-layer bands, `unclassified`
 * included, each present even when empty: a caller decides whether an empty band is a dashed
 * placeholder or reason to skip the chart entirely, this function never hides an absence. */
export function pyramidGraphBands(skills: SkillSummary[]): PyramidGraphBand[] {
  const byLayer = new Map<PyramidLayer, PyramidGraphNode[]>();
  for (const skill of skills) {
    const layer = layerOf(skill);
    byLayer.set(layer, [...(byLayer.get(layer) ?? []), {id: skill.skill_id, label: skill.name, detail: skill.scope}]);
  }
  return knowledgeLayerOrder.map(layer => ({layer, items: byLayer.get(layer) ?? []}));
}

/** The `refines` edges (child -> parent, contract §4.5) among `relations` whose *both* ends are in
 * `skills`. A `refines` edge to a skill outside this scope is a real declared relationship, but
 * not a family tie in this scoped view — it still appears in the caller's full relationship list,
 * never silently dropped, just not drawn here as a dangling connector to a node that is not on
 * the chart. Deduplicated: `relations` can carry the same edge across more than one revision. */
export function pyramidGraphEdges(skills: SkillSummary[], relations: RelationEdge[]): PyramidGraphEdge[] {
  const ids = new Set(skills.map(skill => skill.skill_id));
  const seen = new Set<string>();
  const edges: PyramidGraphEdge[] = [];
  for (const relation of relations) {
    if (relation.type !== 'refines' || !relation.from || !ids.has(relation.from) || !ids.has(relation.to)) continue;
    const key = relation.from + '>' + relation.to;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({from: relation.from, to: relation.to});
  }
  return edges;
}

/** True once at least one skill in this scope carries a real layer — distinct from the fixture's
 * `isFullyUnclassified`, which reads whole-repo bands; this reads a `pyramidGraphBands` result
 * already scoped by the caller. */
export const hasAnyClassification = (bands: PyramidGraphBand[]): boolean =>
  bands.some(band => band.layer !== 'unclassified' && band.items.length > 0);
