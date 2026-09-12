import type {ReactNode, ButtonHTMLAttributes, AnchorHTMLAttributes} from 'react';
import {Link} from 'react-router-dom';
import {Button} from '@/components/ui/button';
import {cn} from '@/lib/utils';
import css from './ActionButton.module.css';

export type ActionTone='neutral'|'system'|'human';
type ButtonProps={tone?:ActionTone;children:ReactNode;className?:string;size?:'default'|'sm'|'icon'}&(
 ({href:string;disabled?:boolean}&Omit<AnchorHTMLAttributes<HTMLAnchorElement>,'href'|'color'>) |
 ({href?:undefined}&Omit<ButtonHTMLAttributes<HTMLButtonElement>,'color'>)
);
/** Tone is the side that acts: human (orange, the one primary action on a screen), system (teal, a read or navigation the service performs), neutral (everything else). */
const variantFor:Record<ActionTone,'default'|'outline'|'secondary'>={neutral:'outline',system:'secondary',human:'default'};
const base='min-h-(--control-height) max-w-full gap-2 rounded-md px-3 text-[length:var(--font-size-body)] font-medium whitespace-normal text-center [&_svg:not([class*=size-])]:size-(--icon-size) focus-visible:ring-0 focus-visible:outline-2 focus-visible:outline-offset-(--focus-offset) focus-visible:outline-human focus-visible:border-transparent';
const toneClass:Record<ActionTone,string>={
 neutral:'border-line-strong bg-graphite-900 text-stone-100 shadow-(--shadow-control) hover:bg-graphite-800 hover:border-(--line-hover) hover:text-stone-100',
 system:'border border-system bg-graphite-900 text-system-ink shadow-(--shadow-control) hover:bg-system-wash hover:text-stone-100',
 human:'bg-human text-graphite-950 hover:bg-human-ink hover:text-graphite-950',
};
export function ActionButton(props:ButtonProps){
 const tone=props.tone||'neutral';
 const size=props.size||'default';
 const className=cn(css.button,base,toneClass[tone],size==='sm'&&'min-h-(--touch-height) sm:min-h-8 px-2.5',size==='icon'&&'w-(--control-height) px-0',props.className);
 if(props.href){
  const {href,tone:_,size:__,disabled,children,className:___,...rest}=props as Extract<ButtonProps,{href:string}>;
  const shared={...rest,className,'data-slot':'button','data-tone':tone,'aria-disabled':disabled||undefined,tabIndex:disabled?-1:rest.tabIndex,onClick:(e:React.MouseEvent<HTMLAnchorElement>)=>{if(disabled)e.preventDefault();else rest.onClick?.(e);}};
  // A disabled link must not retain a target for middle-click or the context menu.
  if(disabled)return <a {...shared} role={rest.role||'link'}>{children}</a>;
  return /^https?:/.test(href)?<a {...shared} href={href} target={rest.target||'_blank'} rel="noopener noreferrer">{children}</a>:<Link {...shared} to={href}>{children}</Link>;
 }
 const {tone:_,size:__,href:___,children,className:____,...rest}=props as Extract<ButtonProps,{href?:undefined}>;
 return <Button {...rest} type={rest.type||'button'} variant={variantFor[tone]} className={className} data-tone={tone}>{children}</Button>;
}
