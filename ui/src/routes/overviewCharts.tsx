/** Overview adapters around the vendored Spectrum UI Charts items (docs/ui/UI.md §7, SC-02).
 * Loaded lazily from HomeRoute so Recharts stays out of the first Overview chunk.
 *
 * Nothing here draws a mark of its own: `BarChart` and `DonutPieChart` are the registry items in
 * `components/spectrumui/charts`, unchanged (their hashes are pinned in qa/spectrum-registry.json).
 * The adapters only shape API counts into the items' data contracts and put the exact values next
 * to the chart as text, because a hover tooltip is never the only way to read a number (SC-05). */
import {BarChart} from '../components/spectrumui/charts/bar-chart';
import {DonutPieChart} from '../components/spectrumui/charts/pie-chart';
import styles from './HomeRoute.module.css';

export interface OverviewBar { key: string; label: string; value: number }
export interface OverviewSlice { key: string; label: string; value: number; fill: string }

const counted = (value: number) => Number.isFinite(value) && value >= 0;

/** A single-series Spectrum bar chart. The registry item always declares two series; the second
 * one is absent (`null`), so Recharts draws no rectangle for it and the Tooltip's default
 * `filterNull` drops it. A `0` there would be a phantom observation, which is why it is not used.
 * Every bar value is a count the caller got from the API; an empty or all-zero set renders nothing
 * and the caller keeps its own text state. */
export function OverviewBarChart({label, bars, color = 'var(--spectrum-chart-1)', horizontal = false}: {label: string; bars: OverviewBar[]; color?: string; horizontal?: boolean}) {
  const rows = bars.filter(bar => counted(bar.value));
  if (!rows.some(bar => bar.value > 0)) return null;
  const data = rows.map(bar => ({category: bar.label, first: bar.value, second: null as unknown as number}));
  return <figure className={styles.chart} aria-label={label}>
    <BarChart data={data} layout={horizontal ? 'horizontal' : 'vertical'} showLegend={false} series={[{label: 'Count', color}, {label: '', color}]} />
  </figure>;
}

/** A Spectrum donut over disjoint parts of one positive total. The caller decides the total is
 * positive and the parts add up to it (SC-03, SC-05); zero-count parts get no slice but stay in the
 * caller's value list, so a known zero is still shown as a number. */
export function OverviewDonutChart({label, slices}: {label: string; slices: OverviewSlice[]}) {
  const rows = slices.filter(slice => counted(slice.value) && slice.value > 0);
  if (!rows.length) return null;
  return <figure className={styles.chart} aria-label={label}>
    <DonutPieChart data={rows.map(slice => ({name: slice.label, value: slice.value, fill: slice.fill}))} showLegend={false} />
  </figure>;
}
