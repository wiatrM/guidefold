import type {ComponentProps} from 'react';
import {sampleSkill as skill} from '../../sample';
import {Panel} from './index';

export default {title:'Guidefold/Panel',component:Panel};
export const Default={args:{title:skill.name,eyebrow:'Immutable source revision',children:<p>{skill.description}</p>} satisfies ComponentProps<typeof Panel>};
