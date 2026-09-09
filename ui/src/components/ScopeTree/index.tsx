import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {Collapsible} from '@base-ui/react/collapsible';
import {CaretRight,FolderSimple,FileText} from '@phosphor-icons/react';
import type {TreeNode} from '../../domain';
import css from './ScopeTree.module.css';

const contains=(node:TreeNode,selected?:string):boolean=>node.id===selected||!!node.children?.some(child=>contains(child,selected));
function Branch({node,depth,selected}:{node:TreeNode;depth:number;selected?:string}){
 const selectedPath=contains(node,selected),automatic=depth===0||selectedPath;
 const [open,setOpen]=useState(automatic);
 useEffect(()=>{if(automatic)setOpen(true);},[automatic,selected]);
 return <Collapsible.Root className={css.branch} open={open} onOpenChange={setOpen} data-selected-path={selectedPath||undefined}>
  <Collapsible.Trigger className={css.branchTrigger}>
   <CaretRight className={css.branchCaret} aria-hidden="true"/><FolderSimple aria-hidden="true"/><span>{node.label}</span>{node.detail&&<small>{node.detail}</small>}
  </Collapsible.Trigger>
  <Collapsible.Panel className={css.branchPanel}><TreeNodes nodes={node.children??[]} depth={depth+1} selected={selected}/></Collapsible.Panel>
 </Collapsible.Root>;
}
function TreeNodes({nodes,depth,selected}:{nodes:TreeNode[];depth:number;selected?:string}){
 return <ul>{nodes.map(node=><li key={node.id}>
  {node.children?.length
   ? <Branch node={node} depth={depth} selected={selected}/>
   : <div className={css.treeLeaf}>
      <FileText aria-hidden="true"/>
      {node.href?<Link to={node.href} aria-current={node.id===selected?'true':undefined}>{node.label}</Link>:<span>{node.label}</span>}
      {node.detail&&<small>{node.detail}</small>}
     </div>}
 </li>)}</ul>;
}
export function ScopeTree({nodes,selected,label}:{nodes:TreeNode[];selected?:string;label:string}){
 return <div className={css.tree} role="group" aria-label={label} data-slot="collapsible"><TreeNodes nodes={nodes} depth={0} selected={selected}/></div>;
}
