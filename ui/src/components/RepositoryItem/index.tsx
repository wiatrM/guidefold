import type {ReactNode} from 'react';
import {Item,ItemContent,ItemTitle,ItemDescription,ItemActions} from '@/components/ui/item';
import {ButtonGroup} from '@/components/ui/button-group';
import {Button} from '@/components/ui/button';
import {HoverCard,HoverCardTrigger,HoverCardContent} from '@/components/ui/hover-card';
import css from './RepositoryItem.module.css';

export interface RepositoryRowAction{label:string;onClick:()=>void;disabled?:boolean}
/**
 * One row of the GitHub repository list (UX §3a): name, the route's own state (a `StateBadge`
 * or similar, passed as `state`), an optional hover preview of the repository, "Import" and any
 * secondary row actions. Wraps shadcn `item`, `hover-card` and `button-group` (2026-09-13); the
 * hover preview also opens on focus (Base UI `PreviewCard`), so it is reachable without a mouse.
 */
export function RepositoryItem({name,detail,state,preview,onImport,importLabel='Import',importDisabled,secondaryActions=[],className}:{name:string;detail?:ReactNode;state?:ReactNode;preview?:ReactNode;onImport?:()=>void;importLabel?:string;importDisabled?:boolean;secondaryActions?:RepositoryRowAction[];className?:string}){
 const title=preview
  ?<HoverCard><HoverCardTrigger className={css.name}>{name}</HoverCardTrigger><HoverCardContent>{preview}</HoverCardContent></HoverCard>
  :<span className={css.name}>{name}</span>;
 return <Item variant="outline" className={className} data-slot="repository-item">
  <ItemContent>
   <ItemTitle>{title}</ItemTitle>
   {detail&&<ItemDescription>{detail}</ItemDescription>}
  </ItemContent>
  <ItemActions className={css.actions}>
   {state}
   <ButtonGroup>
    {onImport&&<Button type="button" size="sm" onClick={onImport} disabled={importDisabled}>{importLabel}</Button>}
    {secondaryActions.map(a=><Button key={a.label} type="button" size="sm" variant="outline" onClick={a.onClick} disabled={a.disabled}>{a.label}</Button>)}
   </ButtonGroup>
  </ItemActions>
 </Item>;
}
