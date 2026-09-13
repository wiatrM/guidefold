import {StateBadge} from '@/components/StateBadge';
import {RepositoryItem} from './index';
export default {title:'Guidefold/RepositoryItem',component:RepositoryItem};
export const ReadyToImport={render:()=> <RepositoryItem name="atlas-search" detail="Last pushed 2 hours ago" state={<StateBadge tone="neutral">Not imported</StateBadge>} onImport={()=>{}} preview={<p>17 skills detected under .agents/skills across 4 scopes.</p>}/>};
export const Imported={render:()=> <RepositoryItem name="atlas-identity" detail="Imported 2026-09-10" state={<StateBadge tone="system">Imported</StateBadge>} secondaryActions={[{label:'Re-import',onClick:()=>{}}]}/>};
