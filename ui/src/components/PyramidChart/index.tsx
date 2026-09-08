import css from './PyramidChart.module.css';

export interface PyramidChartNode {id: string; label: string; detail?: string}
export interface PyramidChartBand {key: 'abstract' | 'task' | 'atomic'; label: string; description: string; items: PyramidChartNode[]}
export interface PyramidChartEdge {from: string; to: string}

const ROW = 100;

/** Places every node at the horizontal centre of its own equal-width slot within its band row —
 * `(index+0.5)/count` of that row's width — so the SVG connector coordinates below line up with
 * the CSS flex row that actually renders the nodes, without ever measuring the DOM: `.bandNodes`
 * gives each item `flex:1`, so its rendered centre lands at exactly that fraction. No
 * ResizeObserver, no layout effect, no measurement race — a pure function of the data. */
function positions(bands: PyramidChartBand[]): Map<string, {x: number; y: number}> {
  const map = new Map<string, {x: number; y: number}>();
  bands.forEach((band, row) => band.items.forEach((item, i) =>
    map.set(item.id, {x: (i + 0.5) / band.items.length * 100, y: row * ROW + ROW / 2})));
  return map;
}

/** Knowledge-layer pyramid for one repository scope: three fixed bands, abstract above task above
 * atomic — unclassified never gets a visual tier here, it is a named absence the caller reports
 * elsewhere, never invented as a fourth band. Each band lists its declared skills as selectable
 * nodes; `edges` (child -> parent `refines`, contract §4.5) draw as connector lines between them.
 * The connector SVG is `aria-hidden`; the caller supplies the accessible text alternative (a
 * relationship table), per `accessibility-contract`. Purely presentational — no `SkillSummary`
 * coupling — so any caller builds `bands`/`edges` from its own source shape. */
export function PyramidChart({bands, edges, selectedId, onSelect}: {
  bands: PyramidChartBand[]; edges: PyramidChartEdge[]; selectedId?: string | null; onSelect?: (id: string) => void;
}) {
  const pos = positions(bands);
  const lines = edges.map(edge => ({edge, a: pos.get(edge.from), b: pos.get(edge.to)})).filter(line => line.a && line.b);
  return <div className={css.chart}>
    <div className={css.graph}>
      <svg className={css.lines} viewBox={'0 0 100 ' + bands.length * ROW} preserveAspectRatio="none" aria-hidden="true">
        {lines.map(({edge, a, b}) => <line key={edge.from + '>' + edge.to} x1={a!.x} y1={a!.y} x2={b!.x} y2={b!.y} stroke="var(--line-strong)" vectorEffect="non-scaling-stroke" />)}
      </svg>
      {bands.map(band => <div key={band.key} className={css.band} data-layer={band.key}>
        <div className={css.bandLabel}><span className={css.bandName}>{band.label}</span><p>{band.description}</p></div>
        {band.items.length
          ? <ul className={css.bandNodes}>{band.items.map(item => <li key={item.id}>
              <button type="button" className={css.node} data-layer={band.key} title={item.detail} aria-current={item.id === selectedId ? 'true' : undefined} onClick={() => onSelect?.(item.id)}>{item.label}</button>
            </li>)}</ul>
          : <p className={css.bandEmpty}>No skill classified at this layer yet.</p>}
      </div>)}
    </div>
  </div>;
}
