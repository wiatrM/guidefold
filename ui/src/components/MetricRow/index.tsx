
import css from './MetricRow.module.css';
import {StatCards} from '../spectrumui/charts/stat-cards';

/** `layout="funnel"`: the five U6 measures of the Usage route in one row (docs/ui/pipeline/04-wireframes.md, 2026-09-07).
 * The only second layout; columns come from tokens.css (`--funnel-metric-columns`), never from the route. */
export function MetricRow({items,layout}:{items:{label:string;value:string;detail:string}[];layout?:'funnel'}){
 return <div data-slot="statistics"><StatCards className={layout==='funnel'?css.funnel:css.metrics} columns={items.length===1?1:items.length===2?2:3} cards={items.map(item=>({label:item.label,displayValue:item.value,caption:item.detail}))}/></div>;
}
