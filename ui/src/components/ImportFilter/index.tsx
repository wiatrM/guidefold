import {ToggleGroup,ToggleGroupItem} from '@/components/ui/toggle-group';
import css from './ImportFilter.module.css';

export type ImportFilterValue='all'|'not_imported'|'imported';
const OPTIONS:{value:ImportFilterValue;label:string}[]=[{value:'all',label:'All'},{value:'not_imported',label:'Not imported'},{value:'imported',label:'Imported'}];
/**
 * The All / Not imported / Imported filter above the GitHub repository list (UX §3a). Wraps
 * shadcn `toggle-group`: single-select (Base UI models selection as a value array, kept to
 * length one here), value always controlled by the route/URL, never local-only state.
 */
export function ImportFilter({value,onChange,counts,className}:{value:ImportFilterValue;onChange:(value:ImportFilterValue)=>void;counts?:Partial<Record<ImportFilterValue,number>>;className?:string}){
 return <ToggleGroup value={[value]} onValueChange={(values)=>{const next=values[0];if(next)onChange(next as ImportFilterValue);}} aria-label="Filter repositories" className={className}>
  {OPTIONS.map(o=><ToggleGroupItem key={o.value} value={o.value}>{o.label}{counts?.[o.value]!==undefined&&<span className={css.count}>{counts[o.value]}</span>}</ToggleGroupItem>)}
 </ToggleGroup>;
}
