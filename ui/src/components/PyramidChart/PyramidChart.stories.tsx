import {PyramidChart} from './index';
export default {title: 'Guidefold/PyramidChart', component: PyramidChart};

const bands = [
  {key: 'abstract' as const, label: 'Abstract', description: 'Concepts and domain knowledge', items: [
    {id: 'data-migration', label: 'Data Migration'},
    {id: 'schema-evolution', label: 'Schema Evolution'},
    {id: 'type-system', label: 'Type System'},
  ]},
  {key: 'task' as const, label: 'Task', description: 'Reusable capabilities and workflows', items: [
    {id: 'migration-plan', label: 'migration-plan'},
    {id: 'object-type-migrations', label: 'object-type-migrations', detail: 'forge.ontology, ontology-team'},
    {id: 'type-mapper', label: 'type-mapper'},
  ]},
  {key: 'atomic' as const, label: 'Atomic', description: 'Concrete, executable elements', items: [
    {id: 'parse-schema', label: 'parse-schema'},
    {id: 'validate-types', label: 'validate-types'},
    {id: 'generate-mapping', label: 'generate-mapping'},
    {id: 'apply-migration', label: 'apply-migration'},
  ]},
];
const edges = [
  {from: 'migration-plan', to: 'schema-evolution'}, {from: 'object-type-migrations', to: 'schema-evolution'}, {from: 'object-type-migrations', to: 'type-system'}, {from: 'type-mapper', to: 'type-system'},
  {from: 'parse-schema', to: 'migration-plan'}, {from: 'validate-types', to: 'migration-plan'}, {from: 'generate-mapping', to: 'type-mapper'}, {from: 'apply-migration', to: 'type-mapper'},
];

export const Family = {args: {bands, edges, selectedId: 'object-type-migrations'}};
export const EmptyAtomicLayer = {args: {
  bands: bands.map(band => band.key === 'atomic' ? {...band, items: []} : band), edges, selectedId: null,
}};
