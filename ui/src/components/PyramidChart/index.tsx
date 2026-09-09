import {lazy,Suspense,useMemo,useState} from 'react';
import {Button} from '@base-ui/react/button';
import {ListBullets,TreeStructure} from '@phosphor-icons/react';
import type {SchemaCard} from './SchemaFlow';
import css from './PyramidChart.module.css';
const SchemaFlow=lazy(()=>import('./SchemaFlow').then(module=>({default:module.SchemaFlow})));
export interface PyramidChartNode {id:string;label:string;detail?:string}
export interface PyramidChartBand {key:'abstract'|'task'|'atomic';label:string;description:string;items:PyramidChartNode[]}
export interface PyramidChartEdge {from:string;to:string}
export function PyramidChart({bands,edges,selectedId,onSelect}: {bands:PyramidChartBand[];edges:PyramidChartEdge[];selectedId?:string|null;onSelect?:(id:string)=>void}) {
 const [mode,setMode]=useState<'graph'|'list'>('graph');
 const cards=useMemo<SchemaCard[]>(()=>bands.flatMap((band,column)=>band.items.map((item,row)=>({id:item.id,title:item.label,kind:band.label,x:column*380,y:row*220,fields:[{name:'scope',value:item.detail||'Not declared'},{name:'layer',value:band.key},{name:'refines',value:String(edges.filter(edge=>edge.from===item.id).length)}]}))),[bands,edges]);
 return <div className={css.chart} data-slot="chart">
  <div className={css.viewToggle} role="group" aria-label="Hierarchy view"><Button aria-pressed={mode==='graph'} onClick={()=>setMode('graph')}><TreeStructure aria-hidden="true"/>Graph</Button><Button aria-pressed={mode==='list'} onClick={()=>setMode('list')}><ListBullets aria-hidden="true"/>List</Button></div>
  {mode==='graph'&&<Suspense fallback={<p className={css.bandEmpty}>Preparing the relationship graph…</p>}><SchemaFlow reverse cards={cards} links={edges.map(edge=>({...edge,label:'refines'}))} selectedId={selectedId} onSelect={onSelect} label="Skill hierarchy"/></Suspense>}
  <div className={mode==='graph'?css.graphLegend:css.listView}>{bands.map(band=><section key={band.key} className={css.band} data-layer={band.key}><div className={css.bandLabel}><h3>{band.label}</h3><span>{band.items.length}</span></div>{mode==='list'&&<p>{band.description}</p>}{!band.items.length?<p className={css.bandEmpty}>No skill classified at this layer yet.</p>:mode==='list'&&<ul className={css.bandNodes}>{band.items.map(item=><li key={item.id}><Button className={css.node} aria-current={item.id===selectedId?'true':undefined} onClick={()=>onSelect?.(item.id)}>{item.label}</Button>{item.detail&&<small>{item.detail}</small>}</li>)}</ul>}</section>)}</div>
 </div>;
}
