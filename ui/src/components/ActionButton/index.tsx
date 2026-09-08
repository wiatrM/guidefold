import type {ReactNode, ButtonHTMLAttributes, AnchorHTMLAttributes} from 'react';
import {Link} from 'react-router-dom';
import css from './ActionButton.module.css';

export type ActionTone='neutral'|'system'|'human';
type ButtonProps={tone?:ActionTone;children:ReactNode;className?:string}&(
 ({href:string;disabled?:boolean}&Omit<AnchorHTMLAttributes<HTMLAnchorElement>,'href'|'color'>) |
 ({href?:undefined}&Omit<ButtonHTMLAttributes<HTMLButtonElement>,'color'>)
);
export function ActionButton(props:ButtonProps){
 const className=[css.button,css[props.tone||'neutral'],props.className||''].join(' ');
 if(props.href){
  const {href,tone:_,disabled,children,className:__,...rest}=props as Extract<ButtonProps,{href:string}>;
  const shared={...rest,className,'aria-disabled':disabled||undefined,tabIndex:disabled?-1:rest.tabIndex,onClick:(e:React.MouseEvent<HTMLAnchorElement>)=>{if(disabled)e.preventDefault();else rest.onClick?.(e);}};
  // A disabled link must not retain a target for middle-click or the context menu.
  if(disabled)return <a {...shared} role={rest.role||'link'}>{children}</a>;
  return /^https?:/.test(href)?<a {...shared} href={href} target={rest.target||'_blank'} rel="noopener noreferrer">{children}</a>:<Link {...shared} to={href}>{children}</Link>;
 }
 const {tone:_,href:__,children,className:___,...rest}=props as Extract<ButtonProps,{href?:undefined}>;
 return <button {...rest} type={rest.type||'button'} className={className}>{children}</button>;
}
