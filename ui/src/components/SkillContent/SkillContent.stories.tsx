import {SkillContent} from './index';
import {sampleSkill as skill} from '../../sample';
export default {title:'Guidefold/SkillContent',component:SkillContent};
export const Default={args:{content:skill.body.split('\n').slice(0,12).join('\n')}};
