import {useId,useState,cloneElement,type ReactElement,type ReactNode,type ButtonHTMLAttributes,type AnchorHTMLAttributes} from 'react';
import {Link} from 'react-router-dom';
import Markdown from 'react-markdown';
import {Copy,Check,FolderSimple,FileText,WarningCircle} from '@phosphor-icons/react';
import type {Tone,DataState,TreeNode,EvidenceEntry} from './domain';
import {lineDiff} from './data';
import css from './Shared.module.css';

type ButtonProps={tone?:Tone;children:ReactNode;className?:string}&(
 ({href:string;disabled?:boolean}&Omit<AnchorHTMLAttributes<HTMLAnchorElement>,'href'|'color'>) |
 ({href?:undefined}&Omit<ButtonHTMLAttributes<HTMLButtonElement>,'color'>)
);
export function ActionButton(props:ButtonProps){
 const className=[css.button,css[props.tone||'neutral'],props.className||''].join(' ');
 if(props.href){
  const {href,tone:_,disabled,children,className:__,...rest}=props as Extract<ButtonProps,{href:string}>;
  const shared={...rest,className,'aria-disabled':disabled||undefined,tabIndex:disabled?-1:rest.tabIndex,onClick:(e:React.MouseEvent<HTMLAnchorElement>)=>{if(disabled)e.preventDefault();else rest.onClick?.(e);}};
  return /^https?:/.test(href)?<a {...shared} href={href} target={rest.target||'_blank'} rel="noopener noreferrer">{children}</a>:<Link {...shared} to={href}>{children}</Link>;
 }
 const {tone:_,href:__,children,className:___,...rest}=props as Extract<ButtonProps,{href?:undefined}>;
 return <button {...rest} type={rest.type||'button'} className={className}>{children}</button>;
}
export function BrandMark(){return <div className={css.brand} data-brand><img src="/assets/guidefold-mark.png" alt="" /><span>Guidefold</span></div>;}
export function Panel({title,eyebrow,icon,action,children,className='',id}:{title:string;eyebrow?:string;icon?:ReactNode;action?:ReactNode;children:ReactNode;className?:string;id?:string}){
 const titleId=useId();return <section id={id} className={[css.panel,className].join(' ')} aria-labelledby={titleId}><header className={css.panelHeader}><div>{eyebrow&&<span className={css.eyebrow}>{eyebrow}</span>}<h2 id={titleId}>{icon&&<span aria-hidden="true">{icon}</span>}{title}</h2></div>{action}</header><div className={css.panelBody}>{children}</div></section>;
}
export function StateBadge({children,tone='neutral'}:{children:ReactNode;tone?:Tone}){return <span className={[css.badge,css[tone]].join(' ')}>{children}</span>;}
export function RouteState({state,title,description,action}:{state:DataState;title:string;description:string;action?:ReactNode}){
 return <section className={css.routeState} aria-busy={state==='loading'} aria-live="polite"><div className={css.stateHeader}>{state==='error'&&<WarningCircle aria-hidden="true" className={css.errorIcon}/>}<h2>{title}</h2></div><p>{description}</p>{state==='loading'&&<div className={css.skeleton} aria-hidden="true"><span/><span/><span/></div>}{action&&<div className={css.stateAction}>{action}</div>}</section>;
}
export function Tabs({label,items,current}:{label:string;items:{id:string;label:string;href:string}[];current:string}){return <nav className={css.tabs} aria-label={label}>{items.map(item=><Link key={item.id} to={item.href} aria-current={current===item.id?'page':undefined}>{item.label}</Link>)}</nav>;}
export function ProvenanceTrail({entries}:{entries:EvidenceEntry[]}){return <dl className={css.evidence}>{entries.map((entry,i)=><div key={entry.label+'-'+i}><dt>{entry.label}</dt><dd className={entry.code?css.mono:undefined}>{entry.href?<a href={entry.href} target="_blank" rel="noopener noreferrer">{entry.value}</a>:entry.value}{entry.detail&&<small>{entry.detail}</small>}</dd></div>)}</dl>;}
export function ScopeTree({nodes,selected,label}:{nodes:TreeNode[];selected?:string;label:string}){
 const contains=(node:TreeNode):boolean=>node.id===selected||!!node.children?.some(contains);
 function renderNodes(items:TreeNode[],depth:number):ReactNode{
  return <ul>{items.map(node=><li key={node.id}>
   {node.children?.length
    ? <details open={depth===0||contains(node)}>
       <summary><FolderSimple aria-hidden="true"/><span>{node.label}</span>{node.detail&&<small>{node.detail}</small>}</summary>
       {renderNodes(node.children,depth+1)}
      </details>
    : <div className={css.treeLeaf}>
       <FileText aria-hidden="true"/>
       {node.href?<Link to={node.href} aria-current={node.id===selected?'true':undefined}>{node.label}</Link>:<span>{node.label}</span>}
       {node.detail&&<small>{node.detail}</small>}
      </div>}
  </li>)}</ul>;
 }
 return <div className={css.tree} role="group" aria-label={label}>{renderNodes(nodes,0)}</div>;
}
export function DataTable({caption,headings,children,className=''}:{caption:string;headings:string[];children:ReactNode;className?:string}){return <div className={[css.tableRegion,className].join(' ')} tabIndex={0} role="region" aria-label={caption}><table className={css.table}><caption>{caption}</caption><thead><tr>{headings.map((h,i)=><th scope="col" key={h+i}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;}
export function SkillDiff({source,candidate}:{source:string;candidate:string}){
 if(source===candidate)return <p className={css.diffQuiet}><StateBadge>No text changes</StateBadge> The candidate matches the exact imported file.</p>;
 return <div className={css.diff}><p>+ Added lines · − Removed lines</p><pre tabIndex={0} aria-label="Source to candidate line diff">{lineDiff(source,candidate).split('\n').map((line,i)=><span key={i} className={line.startsWith('+')?css.diffAdded:line.startsWith('−')?css.diffRemoved:undefined}>{line}{'\n'}</span>)}</pre></div>;
}
export function MetricRow({items}:{items:{label:string;value:string;detail:string}[]}){return <dl className={css.metrics}>{items.map(item=><div key={item.label}><dt>{item.label}</dt><dd>{item.value}<small>{item.detail}</small></dd></div>)}</dl>;}
export function Urn({value}:{value:string}){
 const [notice,setNotice]=useState('');async function copy(){try{await navigator.clipboard.writeText(value);setNotice('Copied identifier');}catch{setNotice('Copy unavailable. Select the identifier text.');}}
 return <div className={css.urn}><code>{value}</code><button type="button" onClick={copy} aria-label="Copy identifier" title="Copy identifier">{notice==='Copied identifier'?<Check aria-hidden="true"/>:<Copy aria-hidden="true"/>}</button><span className={css.copyNotice} role="status">{notice}</span></div>;
}
export function SkillContent({content}:{content:string}){return <div className={css.markdown}><Markdown skipHtml components={{h1:({children})=><h3>{children}</h3>,h2:({children})=><h4>{children}</h4>,h3:({children})=><h5>{children}</h5>,pre:({children})=><pre tabIndex={0} aria-label="Code example">{children}</pre>,a:({children,href})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,img:({alt})=><span>{alt||'Image reference'}</span>}}>{content}</Markdown></div>;}
export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>}){
 const described=[children.props['aria-describedby'],hint?id+'-hint':null,error?id+'-error':null].filter(Boolean).join(' ')||undefined;
 const control=cloneElement(children,{id,'aria-describedby':described,'aria-invalid':error?true:children.props['aria-invalid']});
 return <div className={css.field}><label htmlFor={id}>{label}</label>{control}{hint&&<small id={id+'-hint'}>{hint}</small>}{error&&<p id={id+'-error'} className={css.errorText} role="alert">{error}</p>}</div>;
}
