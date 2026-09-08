import {Urn} from './index';
import fixture from '../../data/fixture.json';
const skill=fixture.skills.find(s=>s.name==='postgres-auth')!;
export default {title:'Guidefold/Urn',component:Urn};
export const Fixture={args:{value:skill.id}};
