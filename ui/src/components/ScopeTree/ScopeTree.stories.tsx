import {MemoryRouter} from 'react-router-dom';
import {ScopeTree} from './index';
import {sampleRepo,sampleSkill as skill,sampleSkills} from '../../sample';
const nodes=[{id:sampleRepo,label:sampleRepo,children:sampleSkills.map(s=>({id:s.id,label:s.name,detail:s.scope,href:'/skill?skill='+encodeURIComponent(s.id)}))}];
export default {title:'Guidefold/ScopeTree',component:ScopeTree};
export const Default={args:{label:'Source excerpts',selected:skill.id,nodes},render:()=> <MemoryRouter><ScopeTree label="Source excerpts" selected={skill.id} nodes={nodes}/></MemoryRouter>};
