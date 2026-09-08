import type {ComponentProps} from 'react';
import fixture from '../../data/fixture.json';
import {Panel} from './index';

const skill=fixture.skills.find(item=>item.name==='postgres-auth')!;
export default {title:'Guidefold/Panel',component:Panel};
export const Fixture={args:{title:skill.name,eyebrow:'Immutable source revision',children:<p>{skill.description}</p>} satisfies ComponentProps<typeof Panel>};
