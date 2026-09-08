import type {Skill} from '../domain';

/** Abstract, task and atomic read general-to-specific; unclassified always sorts last and only
 * appears when the source actually leaves a skill unclassified. */
export const knowledgeLayerOrder = ['abstract', 'task', 'atomic', 'unclassified'] as const;
export type PyramidLayer = typeof knowledgeLayerOrder[number];

export interface PyramidItem {skill: Skill; parentIds: string[]; childIds: string[]}
export interface PyramidBand {layer: PyramidLayer; items: PyramidItem[]}

const layerOf = (skill: Skill): PyramidLayer => {
  const value = skill.knowledgeLayer.trim().toLowerCase();
  return value === 'abstract' || value === 'task' || value === 'atomic' ? value : 'unclassified';
};

/** Groups skills into knowledge-layer bands and attaches each skill's declared family: the
 * `refines` parents it names and the ids of the skills that in turn refine it. A band with no
 * skill is omitted entirely — never rendered empty. Nothing here infers a layer or a relation
 * the source did not declare; a skill with no recognised layer value joins `unclassified`. */
export function pyramidBands(skills: Skill[]): PyramidBand[] {
  const childIdsOf = new Map<string, string[]>();
  for (const skill of skills) for (const parentId of skill.refines) {
    childIdsOf.set(parentId, [...(childIdsOf.get(parentId) ?? []), skill.id]);
  }
  const byLayer = new Map<PyramidLayer, PyramidItem[]>();
  for (const skill of skills) {
    const layer = layerOf(skill);
    const item: PyramidItem = {skill, parentIds: skill.refines, childIds: childIdsOf.get(skill.id) ?? []};
    byLayer.set(layer, [...(byLayer.get(layer) ?? []), item]);
  }
  return knowledgeLayerOrder.filter(layer => byLayer.has(layer)).map(layer => ({layer, items: byLayer.get(layer) as PyramidItem[]}));
}

/** True when every skill fell into `unclassified` — the case the fixture is in today, before a
 * generator populates real layer values. The caller shows one explanatory line instead of N
 * repeated "Unclassified" captions in this case. */
export const isFullyUnclassified = (bands: PyramidBand[]): boolean => bands.length === 1 && bands[0].layer === 'unclassified';
