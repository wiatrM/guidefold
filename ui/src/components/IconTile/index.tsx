import type {ReactNode} from 'react';
import {motion,useReducedMotion} from 'motion/react';
import {cn} from '@/lib/utils';
import css from './IconTile.module.css';

export type TileTone='system'|'human'|'neutral';
export type TileSize='sm'|'md'|'lg'|'xl';

/**
 * One large glyph on a graphite survey grid. The console's single memorable device: page
 * headers, quickstart steps and empty states put the icon first so a view is recognised
 * before its title is read. Decorative by default (`aria-hidden`); pass `label` only when the
 * tile is the sole carrier of meaning, e.g. inside an icon-only link.
 */
export function IconTile({icon,size='md',tone='system',label,animate=true,className}:{icon:ReactNode;size?:TileSize;tone?:TileTone;label?:string;animate?:boolean;className?:string}){
 const reduce=useReducedMotion();
 const still=reduce||!animate;
 return <motion.span className={cn(css.tile,css[size],css[tone],className)} data-slot="icon-tile" data-tone={tone} data-size={size} role={label?'img':undefined} aria-label={label} aria-hidden={label?undefined:true}
  initial={still?false:{opacity:0,scale:0.92}} animate={{opacity:1,scale:1}} transition={{duration:still?0:0.32,ease:[0.16,1,0.3,1]}}>
  <span className={css.glyph}>{icon}</span>
 </motion.span>;
}
