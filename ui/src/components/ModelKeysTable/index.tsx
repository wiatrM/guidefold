import {Table,TableHeader,TableBody,TableRow,TableHead,TableCell,TableCaption} from '@/components/ui/table';
import {Button} from '@/components/ui/button';
import {StateBadge} from '@/components/StateBadge';
import css from './ModelKeysTable.module.css';

export interface ModelKey{id:string;provider:string;lastFour:string;preferred?:boolean}
/**
 * Organization > Model keys: provider, the masked secret (last four characters only, never the
 * full key) and which key is preferred. Wraps the console's own shadcn `table` primitive
 * (2026-09-13); it does not use `@spectrumui/data-table` — that 84 KB self-contained item
 * duplicates a table/checkbox already in this design system and ships its own non-lucide icon
 * set (docs/reports/ui/premium-components-20260913.md records the rejection).
 */
export function ModelKeysTable({keys,onDelete,onSetPreferred,className}:{keys:ModelKey[];onDelete?:(id:string)=>void;onSetPreferred?:(id:string)=>void;className?:string}){
 return <Table className={className}>
  <TableCaption>Model keys for this organisation</TableCaption>
  <TableHeader><TableRow><TableHead>Provider</TableHead><TableHead>Key</TableHead><TableHead>Preferred</TableHead><TableHead className={css.actions}>Actions</TableHead></TableRow></TableHeader>
  <TableBody>
   {keys.map(k=><TableRow key={k.id}>
    <TableCell>{k.provider}</TableCell>
    <TableCell><code className={css.masked}>{'••••'}{k.lastFour}</code></TableCell>
    <TableCell>{k.preferred?<StateBadge tone="system">Preferred</StateBadge>:onSetPreferred?<Button type="button" size="sm" variant="outline" onClick={()=>onSetPreferred(k.id)}>Make preferred</Button>:null}</TableCell>
    <TableCell>{onDelete&&<Button type="button" size="sm" variant="outline" onClick={()=>onDelete(k.id)}>Delete</Button>}</TableCell>
   </TableRow>)}
   {!keys.length&&<TableRow><TableCell colSpan={4}>No model keys yet.</TableCell></TableRow>}
  </TableBody>
 </Table>;
}
