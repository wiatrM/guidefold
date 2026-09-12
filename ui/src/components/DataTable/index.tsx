import type {ReactNode} from 'react';
import {TableHeader,TableBody,TableRow,TableHead,TableCaption} from '@/components/ui/table';
import {cn} from '@/lib/utils';
import css from './DataTable.module.css';

/**
 * A captioned table on shadcn Table. The caption names the scrollable region; rows are the
 * route's own <tr> elements so cells keep their semantics (row headers, badges, links).
 *
 * `flush` (second pass 2026-09-12): inside a Panel the card already draws the frame, so a
 * second ring and a visible caption read as a box in a box. The caption stays for assistive
 * technology (sr-only) and as the region name; only the chrome goes.
 */
export function DataTable({caption,headings,children,className='',dense,flush}:{caption:string;headings:string[];children:ReactNode;className?:string;dense?:boolean;flush?:boolean}){
 return <div className={cn(css.tableRegion,flush?'rounded-none':'rounded-lg border border-line-strong bg-graphite-900 shadow-(--shadow-card)',className)} tabIndex={0} role="region" aria-label={caption}>
  {/* The region above is the one scroll container and is focusable; shadcn's Table wrapper would nest a second, unfocusable one (axe scrollable-region-focusable). */}
  <table data-slot="table" className={cn(css.table,'w-full caption-top text-[length:var(--font-size-small)]',dense&&css.dense)}>
   <TableCaption className={cn('mt-0 px-2 py-2 text-left text-stone-300',flush&&'sr-only')}>{caption}</TableCaption>
   <TableHeader className="[&_tr]:border-line"><TableRow className="hover:bg-transparent">{headings.map((h,i)=><TableHead scope="col" key={h+i} className={cn('h-(--row-height) px-2 font-semibold text-stone-300',flush?'bg-transparent border-b border-line':'bg-graphite-850')}>{h}</TableHead>)}</TableRow></TableHeader>
   <TableBody className={css.body}>{children}</TableBody>
  </table>
 </div>;
}
