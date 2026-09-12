import {useId,useState, type ReactNode} from 'react';
import {CaretDownIcon} from '@phosphor-icons/react';
import {Card,CardHeader,CardTitle,CardDescription,CardAction,CardContent} from '@/components/ui/card';
import {Collapsible,CollapsibleTrigger,CollapsibleContent} from '@/components/ui/collapsible';
import {cn} from '@/lib/utils';
import css from './Panel.module.css';

/**
 * A named region on shadcn Card. The heading is the region name (aria-labelledby), the
 * eyebrow is a short qualifier under it, `action` sits in the header's action slot. A
 * small icon tints the title; large icons belong to IconTile placed by the route.
 *
 * Second pass 2026-09-12 (progressive disclosure, written reason: a page of six equal cards
 * overwhelms; secondary evidence folds away and the one thing to do stays in view):
 * - `collapsible` adds a caret button in the header; the body stays mounted (keepMounted) so
 *   text, focus targets and tests survive a fold, and `defaultOpen` says how it starts.
 * - `tone="quiet"` drops the card ring for a hairline rule, for sections that are context,
 *   not a unit of work. Default stays the card.
 */
export function Panel({title,eyebrow,icon,action,children,className='',id,size,collapsible=false,defaultOpen=true,tone='card'}:{title:string;eyebrow?:string;icon?:ReactNode;action?:ReactNode;children:ReactNode;className?:string;id?:string;size?:'default'|'sm';collapsible?:boolean;defaultOpen?:boolean;tone?:'card'|'quiet'}){
 const titleId=useId();
 const bodyId=useId();
 const [open,setOpen]=useState(defaultOpen);
 const quiet=tone==='quiet';
 const header=<CardHeader className={cn(css.header,'py-(--card-spacing)',quiet?'border-b border-line px-0':'border-b border-line',collapsible&&!open&&'border-b-0')}>
  <CardTitle render={<h2 id={titleId}/>} className={cn(css.title,'flex items-center gap-2 font-display text-[length:var(--font-size-section)] font-semibold tracking-(--tracking-title)')}>{icon&&<span aria-hidden="true" className="inline-flex text-system">{icon}</span>}{title}</CardTitle>
  {eyebrow&&<CardDescription className="font-display text-[length:var(--font-size-small)] font-medium">{eyebrow}</CardDescription>}
  {(action||collapsible)&&<CardAction className="flex items-center gap-2">{action}{collapsible&&<CollapsibleTrigger className={cn(css.fold,'group inline-flex h-(--control-height) w-(--control-height) cursor-pointer items-center justify-center rounded-md border-0 bg-transparent text-stone-300 hover:bg-graphite-800 hover:text-stone-100')} aria-controls={bodyId} aria-label={(open?'Collapse ':'Expand ')+title}><CaretDownIcon aria-hidden="true" className="transition-transform duration-(--duration-menu) group-data-[panel-open]:rotate-180 motion-reduce:transition-none"/></CollapsibleTrigger>}</CardAction>}
 </CardHeader>;
 const body=<CardContent className={cn(css.body,'py-(--card-spacing)',quiet&&'px-0')}>{children}</CardContent>;
 const shell=cn(css.panel,'gap-0 py-0',quiet?'rounded-none bg-transparent shadow-none ring-0':'ring-line-strong shadow-(--shadow-card)',className);
 if(!collapsible)return <Card render={<section id={id} aria-labelledby={titleId}/>} size={size} className={shell}>{header}{body}</Card>;
 return <Collapsible open={open} onOpenChange={setOpen} render={<Card render={<section id={id} aria-labelledby={titleId}/>} size={size} className={shell}/>} data-slot="panel-collapsible">
  {header}
  <CollapsibleContent id={bodyId} keepMounted className={css.foldBody}>{body}</CollapsibleContent>
 </Collapsible>;
}
