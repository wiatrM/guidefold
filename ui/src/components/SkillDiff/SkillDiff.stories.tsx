import {SkillDiff} from './index';
import fixture from '../../data/fixture.json';
const skill=fixture.skills.find(s=>s.name==='postgres-auth')!;
const candidate=skill.raw.replace('cache 30','cache 60')===skill.raw?skill.raw.replace('30','60'):skill.raw.replace('cache 30','cache 60');
export default {title:'Guidefold/SkillDiff',component:SkillDiff};
export const Fixture={args:{source:skill.raw,candidate}};
