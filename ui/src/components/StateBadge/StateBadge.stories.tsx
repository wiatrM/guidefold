import {StateBadge} from './index';
export default {title:'Guidefold/StateBadge',component:StateBadge};
// The five existing semantic roles are text-labelled; no new visual variant.
export const Fixture={render:()=> <><StateBadge>Unknown</StateBadge>{' '}<StateBadge tone="system">Published</StateBadge>{' '}<StateBadge tone="human">Approved for export</StateBadge>{' '}<StateBadge tone="warning">Partial</StateBadge>{' '}<StateBadge tone="error">Failed</StateBadge></>};
