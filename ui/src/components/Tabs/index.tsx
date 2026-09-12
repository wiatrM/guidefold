import {Link} from 'react-router-dom';
import {motion,useReducedMotion} from 'motion/react';
import {cn} from '@/lib/utils';
import css from './Tabs.module.css';

/**
 * Section tabs that are links: the selected section lives in the URL (07 §navigation), so
 * Back, bookmarks and the address bar all work and no tablist state can drift from it. The
 * marker glides between links (layoutId) and stands still under reduced motion.
 */
export function Tabs({label,items,current}:{label:string;items:{id:string;label:string;href:string}[];current:string}){
 const reduce=useReducedMotion();
 return <nav className={cn(css.tabs,'flex flex-wrap items-center gap-1 border-b border-line-strong')} aria-label={label} data-slot="tabs-list" data-variant="line">
  {items.map(item=>{const active=current===item.id;return <Link key={item.id} to={item.href} aria-current={active?'page':undefined} data-slot="tabs-trigger" data-active={active||undefined} className={cn(css.tab,'relative inline-flex min-h-(--control-height) items-center gap-2 rounded-t-md px-3 py-2 no-underline transition-colors hover:bg-graphite-800 hover:text-stone-100')}>
   {item.label}
   {active&&<motion.span layoutId={'tabs-marker-'+label} className={css.marker} aria-hidden="true" transition={reduce?{duration:0}:{type:'spring',visualDuration:0.24,bounce:0}}/>}
  </Link>;})}
 </nav>;
}
