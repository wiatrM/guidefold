import {MemoryRouter} from 'react-router-dom';
import {ScopeTree} from './index';
import fixture from '../../data/fixture.json';
const skill=fixture.skills.find(s=>s.name==='postgres-auth')!;
const nodes=[{id:fixture.repo,label:fixture.repo,children:[skill,...fixture.skills.slice(0,2)].map(s=>({id:s.id,label:s.name,detail:s.scope,href:'/skill?skill='+encodeURIComponent(s.id)}))}];
export default {title:'Guidefold/ScopeTree',component:ScopeTree};
export const Fixture={args:{label:'Fixture source excerpts',selected:skill.id,nodes},render:()=> <MemoryRouter><ScopeTree label="Fixture source excerpts" selected={skill.id} nodes={nodes}/></MemoryRouter>};
