import {Books,GitPullRequest,TreeStructure} from '@phosphor-icons/react';
import {IconTile} from './index';

export default {title:'Guidefold/IconTile',component:IconTile};
// Three tones, four sizes; the glyph is the only thing that changes between views.
export const Default={render:()=> <><IconTile icon={<Books weight="duotone"/>} size="sm"/>{' '}<IconTile icon={<Books weight="duotone"/>}/>{' '}<IconTile icon={<TreeStructure weight="duotone"/>} size="lg" tone="human"/>{' '}<IconTile icon={<GitPullRequest weight="duotone"/>} size="xl" tone="neutral" label="Proposals"/></>};
