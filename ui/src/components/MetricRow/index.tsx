
import css from './MetricRow.module.css';

/** `layout="funnel"`: the five U6 measures of the Usage route in one row (docs/ui/pipeline/04-wireframes.md, 2026-09-07).
 * The only second layout; columns come from tokens.css (`--funnel-metric-columns`), never from the route. */
export function MetricRow({items,layout}:{items:{label:string;value:string;detail:string}[];layout?:'funnel'}){return <dl className={[css.metrics,layout==='funnel'?css.funnel:''].join(' ').trim()}>{items.map(item=><div key={item.label}><dt>{item.label}</dt><dd>{item.value}<small>{item.detail}</small></dd></div>)}</dl>;}
