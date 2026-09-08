import {DataTable} from './index';
import {StateBadge} from '../StateBadge';
import fixture from '../../data/fixture.json';
const skill=fixture.skills.find(s=>s.name==='postgres-auth')!;
export default {title:'Guidefold/DataTable',component:DataTable};
export const Fixture={args:{caption:'Meridian fixture source revisions',headings:['Skill','Scope','Source status'],children:[skill,...fixture.skills.slice(0,2)].map(s=><tr key={s.id}><th scope="row">{s.name}</th><td>{s.scope}</td><td><StateBadge>{s.sourceStatus}</StateBadge></td></tr>)}};
