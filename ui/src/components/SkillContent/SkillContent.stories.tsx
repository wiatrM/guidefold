import {SkillContent} from './index';
import fixture from '../../data/fixture.json';
const skill=fixture.skills.find(s=>s.name==='postgres-auth')!;
export default {title:'Guidefold/SkillContent',component:SkillContent};
export const Fixture={args:{content:skill.body.split('\n').slice(0,12).join('\n')}};
