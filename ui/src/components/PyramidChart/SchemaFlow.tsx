import {memo, useEffect, useMemo, useRef, useState} from 'react';
import {ReactFlow, ReactFlowProvider, Handle, Position, Controls, MarkerType, useReactFlow, type Node, type NodeProps, type Edge} from '@xyflow/react';
import {useReducedMotion} from 'motion/react';
import {Database, Pause, Play, ArrowsOutSimple} from '@phosphor-icons/react';
import {Button} from '@base-ui/react/button';
import '@xyflow/react/dist/style.css';
import css from './PyramidChart.module.css';

export interface SchemaField {name:string;value:string}
export interface SchemaCard {id:string;title:string;kind:string;fields:SchemaField[];x:number;y:number}
export interface SchemaLink {from:string;to:string;label?:string}
type SchemaNode=Node<{card:SchemaCard;active:boolean;reverse:boolean;onSelect?: (id:string)=>void}&Record<string,unknown>,'schema'>;
/** Adapted from xyflow's MIT Database Schema Node registry recipe:
 * https://ui.reactflow.dev/database-schema-node. Header, table and handles are
 * retained; CSS Modules apply Guidefold tokens instead of Tailwind classes. */
const SchemaNodeView=memo(function SchemaNodeView({data}:NodeProps<SchemaNode>){
 const {card,active,onSelect,reverse}=data;
 return <article className={css.schemaNode} data-active={active} data-kind={card.kind} data-slot="database-schema-node">
  <Handle type="target" position={reverse?Position.Right:Position.Left} id="input" isConnectable={false} className={css.handle}/>
  <header className={css.schemaHeader}><Database aria-hidden="true"/><div><span>{card.kind}</span><h3>{onSelect?<button type="button" className={css.schemaSelect} aria-current={active?'true':undefined} onClick={()=>onSelect(card.id)}>{card.title}</button>:card.title}</h3></div></header>
  <table className={css.schemaTable} aria-label={card.title+' fields'}><tbody>{card.fields.map(field=><tr key={field.name}><th scope="row">{field.name}</th><td title={field.value}>{field.value}</td></tr>)}</tbody></table>
  <Handle type="source" position={reverse?Position.Left:Position.Right} id="output" isConnectable={false} className={css.handle}/>
 </article>;
});
const nodeTypes={schema:SchemaNodeView};
function ResponsiveFrame({selectedId,firstId,count}:{selectedId?:string|null;firstId?:string;count:number}){
 const {fitBounds,getNode,viewportInitialized:ready}=useReactFlow();
 useEffect(()=>{
  const frame=()=>{
   if(!ready)return;
   const narrow=window.matchMedia('(max-width: 720px)').matches;
   const id=selectedId||firstId;
   const node=id?getNode(id):undefined;
   if(node&&(narrow||count>8))void fitBounds({x:node.position.x,y:node.position.y,width:node.measured?.width??280,height:node.measured?.height??220},{padding:0.15});
  };
  frame();window.addEventListener('resize',frame);return()=>window.removeEventListener('resize',frame);
 },[ready,selectedId,firstId,count,fitBounds,getNode]);
 return null;
}
export function SchemaFlow({cards,links,selectedId,onSelect,label,explanatory=false,reverse=false}:{cards:SchemaCard[];links:SchemaLink[];selectedId?:string|null;onSelect?:(id:string)=>void;label:string;explanatory?:boolean;reverse?:boolean}){
 const reduce=useReducedMotion();
 const [playing,setPlaying]=useState(explanatory),[visible,setVisible]=useState(false);
 const host=useRef<HTMLDivElement>(null);
 useEffect(()=>{const observer=new IntersectionObserver(([entry])=>setVisible(entry.isIntersecting));if(host.current)observer.observe(host.current);return()=>observer.disconnect();},[]);
 const moving=playing&&visible&&!reduce;
 const nodes=useMemo<SchemaNode[]>(()=>cards.map(card=>({id:card.id,type:'schema',position:{x:card.x,y:card.y},data:{card,active:card.id===selectedId,onSelect,reverse},ariaLabel:card.title,draggable:false,selectable:false,focusable:false})),[cards,selectedId,onSelect,reverse]);
 const edges=useMemo<Edge[]>(()=>{const ids=new Set(cards.map(card=>card.id));return links.filter(link=>ids.has(link.from)&&ids.has(link.to)).map((link,index)=>({id:link.from+'>'+link.to+':'+index,source:link.from,target:link.to,sourceHandle:'output',targetHandle:'input',type:'smoothstep',label:link.label,animated:moving,markerEnd:{type:MarkerType.ArrowClosed}}));},[cards,links,moving]);
 return <div ref={host} className={css.flowShell} data-slot="schema-flow" data-animated={moving}>
  <div className={css.flowToolbar}><span><ArrowsOutSimple aria-hidden="true"/>{label}</span><Button className={css.motionButton} onClick={()=>setPlaying(value=>!value)} disabled={Boolean(reduce)} aria-pressed={playing} aria-label={playing?'Pause flow animation':'Play flow animation'}>{playing&&!reduce?<Pause aria-hidden="true"/>:<Play aria-hidden="true"/>}{reduce?'Reduced motion':playing?'Pause':'Animate'}</Button></div>
  <div className={css.flowCanvas} role="region" aria-label={label}><ReactFlowProvider><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} colorMode="dark" fitView fitViewOptions={{padding:0.15}} minZoom={0.15} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} edgesFocusable={false} deleteKeyCode={null} zoomOnScroll={false} preventScrolling={false} ariaLabelConfig={{'node.a11yDescription.default':'Press Enter to inspect this skill.','controls.fitView.ariaLabel':'Fit all nodes'}}><ResponsiveFrame selectedId={selectedId} firstId={cards[0]?.id} count={cards.length}/><Controls orientation="horizontal" showInteractive={false}/></ReactFlow></ReactFlowProvider></div>
 </div>;
}
