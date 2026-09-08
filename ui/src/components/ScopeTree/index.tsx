import {useEffect,useRef,type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import {FolderSimple,FileText} from '@phosphor-icons/react';
import type {TreeNode} from '../../domain';
import css from './ScopeTree.module.css';

export function ScopeTree({nodes,selected,label}:{nodes:TreeNode[];selected?:string;label:string}){
 const root=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  let branch=root.current?.querySelector('[aria-current="true"]')?.closest('details');
  while(branch){branch.open=true;branch=branch.parentElement?.closest('details')||null;}
 },[selected]);
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
 return <div ref={root} className={css.tree} role="group" aria-label={label}>{renderNodes(nodes,0)}</div>;
}
