import type {ReactNode} from 'react';
import {WarningCircleIcon,LockSimpleIcon,TrayIcon,CircleDashedIcon,WifiSlashIcon} from '@phosphor-icons/react';
import {Empty,EmptyHeader,EmptyMedia,EmptyTitle,EmptyDescription,EmptyContent} from '@/components/ui/empty';
import {Skeleton} from '@/components/ui/skeleton';
import {IconTile} from '../IconTile';
import {cn} from '@/lib/utils';
import type {DataState} from '../../domain';
import css from './RouteState.module.css';

const media:Record<DataState,{icon:ReactNode;tone:'system'|'human'|'neutral'}>={
 ready:{icon:<CircleDashedIcon weight="duotone"/>,tone:'neutral'},
 empty:{icon:<TrayIcon weight="duotone"/>,tone:'neutral'},
 loading:{icon:<CircleDashedIcon weight="duotone"/>,tone:'system'},
 partial:{icon:<WarningCircleIcon weight="duotone"/>,tone:'human'},
 error:{icon:<WarningCircleIcon weight="duotone"/>,tone:'human'},
 degraded:{icon:<WifiSlashIcon weight="duotone"/>,tone:'human'},
 restricted:{icon:<LockSimpleIcon weight="duotone"/>,tone:'neutral'},
};
/**
 * The six non-ready states of a route (07 §states). One tile, a heading, one sentence that says
 * what is and is not known, and the single action that can change it. Loading shows the shape
 * of the rows that are coming; nothing here ever reads as a value.
 *
 * `compact` (second pass 2026-09-12): the same words on one line beside a medium tile, for an
 * empty section inside a page that already has a full state above it. Five towering empty
 * cards on one screen were the overwhelm; one full and the rest compact is the fix.
 */
export function RouteState({state,title,description,action,compact=false}:{state:DataState;title:string;description:string;action?:ReactNode;compact?:boolean}){
 const {icon,tone}=media[state];
 return <section className={css.routeState} aria-busy={state==='loading'} aria-live="polite" data-slot="alert" data-state={state} data-compact={compact||undefined}>
  <Empty className={cn('rounded-lg border border-line-strong bg-graphite-900 text-left shadow-(--shadow-card)',compact?'flex-row flex-wrap items-center gap-3 p-(--space-3)':'items-start p-(--space-4)')}>
   <EmptyHeader className={cn('max-w-(--reading-width) items-start',compact&&'flex-row items-center gap-3')}>
    <EmptyMedia className={compact?'mb-0':'mb-1'}><IconTile icon={icon} tone={tone} size={compact?'md':'lg'} animate={state!=='loading'&&!compact}/></EmptyMedia>
    <div className={cn(compact&&'grid gap-0.5')}>
     <EmptyTitle render={<h2/>} className={cn(css.title,compact&&css.compactTitle)}>{title}</EmptyTitle>
     <EmptyDescription render={<p/>} className="m-0 text-left text-[length:var(--font-size-body)] text-stone-300">{description}</EmptyDescription>
    </div>
   </EmptyHeader>
   {state==='loading'&&<div className={css.skeleton} aria-hidden="true" data-slot="skeleton-group"><Skeleton className="h-(--row-height) w-full rounded-md bg-graphite-800"/><Skeleton className="h-(--row-height) w-4/5 rounded-md bg-graphite-800"/><Skeleton className="h-(--row-height) w-3/5 rounded-md bg-graphite-800"/></div>}
   {action&&<EmptyContent className={cn('items-start',compact&&'w-auto max-w-none flex-row sm:ml-auto')}>{action}</EmptyContent>}
  </Empty>
 </section>;
}
