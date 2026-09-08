import type {ComponentProps} from 'react';
import {sampleSkill as skill,sampleSourceUrl} from '../../sample';
import {ProvenanceTrail} from './index';
export default {title:'Guidefold/ProvenanceTrail',component:ProvenanceTrail};
export const Default={args:{entries:[{label:'Scope',value:skill.scope},{label:'Owner',value:skill.owner},{label:'Revision SHA-256',value:skill.revision,code:true},{label:'Exact source',value:skill.path,href:sampleSourceUrl(skill.path),code:true}]} satisfies ComponentProps<typeof ProvenanceTrail>};
