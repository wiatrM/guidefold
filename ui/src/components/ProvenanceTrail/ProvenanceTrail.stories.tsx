import type {ComponentProps} from 'react';
import fixture from '../../data/fixture.json';
import {ProvenanceTrail} from './index';
const skill=fixture.skills.find(item=>item.name==='postgres-auth')!;
export default {title:'Guidefold/ProvenanceTrail',component:ProvenanceTrail};
export const Fixture={args:{entries:[{label:'Scope',value:skill.scope},{label:'Owner',value:skill.owner},{label:'Revision SHA-256',value:skill.revision,code:true},{label:'Exact source',value:skill.path,href:'https://github.com/wiatrM/guidefold/blob/'+fixture.commit+'/examples/monorepo/'+skill.path,code:true}]} satisfies ComponentProps<typeof ProvenanceTrail>};
