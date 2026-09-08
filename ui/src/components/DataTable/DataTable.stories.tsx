import {DataTable} from './index';
import {StateBadge} from '../StateBadge';
import {sampleSkills} from '../../sample';
export default {title:'Guidefold/DataTable',component:DataTable};
export const Default={args:{caption:'Sample source revisions',headings:['Skill','Scope','Source status'],children:sampleSkills.map(s=><tr key={s.id}><th scope="row">{s.name}</th><td>{s.scope}</td><td><StateBadge>{s.sourceStatus}</StateBadge></td></tr>)}};
