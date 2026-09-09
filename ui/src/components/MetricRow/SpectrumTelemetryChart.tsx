import {BarChart} from './spectrumui/charts/bar-chart';
import {DonutPieChart} from './spectrumui/charts/pie-chart';
import css from './SpectrumTelemetryChart.module.css';

/** Product adapter around the Spectrum UI Charts registry bar item. */
export type SpectrumTelemetryPoint = {
  id: string;
  label: string;
  value: number;
  trackValue?: number;
  detail: string;
  color?: string;
};

type SpectrumTelemetryChartProps = {points: SpectrumTelemetryPoint[]; max?: number; ariaLabel: string; emptyLabel?: string};
const safeValue = (value: number) => Number.isFinite(value) && value > 0 ? value : 0;

export function SpectrumTelemetryChart({points, max, ariaLabel, emptyLabel = 'No measured data in this window.'}: SpectrumTelemetryChartProps) {
  const normalized = points.map(point => ({...point, value: safeValue(point.value), trackValue: safeValue(point.trackValue ?? point.value)}));
  const scale = Math.max(0, max ?? 0, ...normalized.flatMap(point => [point.value, point.trackValue ?? 0]));
  if (scale === 0 || normalized.length === 0) return <p className={css.empty}>{emptyLabel}</p>;
  const data = normalized.map(point => ({month: point.label, desktop: point.trackValue, mobile: point.value}));
  return <div className={css.spectrumAdapter} role="group" aria-label={ariaLabel}>
    <BarChart data={data} layout="horizontal" showLegend={false} showGrid={false} hideAxisLabels />
    <ul className={css.accessibleValues}>{normalized.map(point => <li key={point.id}><strong>{point.label}</strong><span>{point.detail}</span></li>)}</ul>
    <span className={css.chartScale} aria-hidden="true">Scale max {scale}</span>
  </div>;
}

export type SpectrumTelemetryStack = {id: string; label: string; value: number; color: string};
type SpectrumTelemetryStackedBarProps = {segments: SpectrumTelemetryStack[]; ariaLabel: string; totalLabel: string};

/** Product adapter around the Spectrum UI Charts registry pie item for verdict shares. */
export function SpectrumTelemetryStackedBar({segments, ariaLabel, totalLabel}: SpectrumTelemetryStackedBarProps) {
  const normalized = segments.map(segment => ({...segment, value: safeValue(segment.value)}));
  const total = normalized.reduce((sum, segment) => sum + segment.value, 0);
  if (total === 0) return <p className={css.empty}>{totalLabel}</p>;
  return <div className={css.spectrumAdapter} role="group" aria-label={ariaLabel}>
    <DonutPieChart data={normalized.filter(segment => segment.value > 0).map(segment => ({name: segment.label, value: segment.value}))} showLegend={false} />
    <ul className={css.accessibleValues}>{normalized.map(segment => <li key={segment.id}><strong>{segment.label}</strong><span>{segment.value}</span></li>)}</ul>
    <p className={css.detail}>{totalLabel}</p>
  </div>;
}
