/*
 * Spectrum UI Charts registry adapter.
 * Source: https://ui.spectrumhq.in/charts/ (chart-kit item, retrieved 2026-09-09).
 * Guidefold adapts the registry source to CSS Modules and its token layer; chart
 * rendering remains Recharts + framer-motion as supplied by the registry.
 */
'use client';

import * as React from 'react';
import {motion, useReducedMotion} from 'framer-motion';
import {Rectangle} from 'recharts';
import {CartesianGrid, XAxis, YAxis} from 'recharts';
import css from './SpectrumCharts.module.css';

export const MONTHLY_TRAFFIC = [{month: 'Jan', desktop: 186, mobile: 80}];
export const BROWSER_SHARE = [{name: 'Other', value: 1}];
export const SERIES = {desktop: {label: 'Track', color: 'var(--spectrum-chart-1)'}, mobile: {label: 'Value', color: 'var(--spectrum-chart-2)'}} as const;
export const CHART_COLORS = ['var(--spectrum-chart-1)', 'var(--spectrum-chart-2)', 'var(--spectrum-chart-3)', 'var(--spectrum-chart-4)', 'var(--spectrum-chart-5)'] as const;
export const EASE_OUT = [0.23, 1, 0.32, 1] as const;
export const BAR_STAGGER = 0.04;
export const BAR_GROW = 0.22;
export const HOVER_MS = 160;
export const HOVER_OPACITY = 0.28;
export const HOVER_TRANSITION = `opacity ${HOVER_MS}ms cubic-bezier(0.23, 1, 0.32, 1)`;

export type BarFillVariant = 'default' | 'hatched' | 'duotone' | 'duotone-reverse' | 'gradient' | 'stripped';
export function cn(...values: Array<string | undefined | false | null>) { return values.filter(Boolean).join(' '); }
export function useChartId(prefix = 'chart') { return `${prefix}-${React.useId().replace(/:/g, '')}`; }
export function useChartMotion() { const reduce = Boolean(useReducedMotion()); return {reduce, isAnimationActive: !reduce, animationDuration: reduce ? 0 : 220, ease: EASE_OUT}; }
export function useIntroStartedAt() { const [started] = React.useState(() => Date.now()); return started; }

const HoverIndexContext = React.createContext<number | null>(null);
export function HoverIndexProvider({value, children}: {value: number | null; children: React.ReactNode}) { return <HoverIndexContext.Provider value={value}>{children}</HoverIndexContext.Provider>; }
export function readActiveTooltipIndex(state: {activeTooltipIndex?: number | string | null}) { return typeof state.activeTooltipIndex === 'number' ? state.activeTooltipIndex : null; }
export const chartVarsClassName = css.chartVars;
export const chartVarsNeutral = css.chartVars;
export function ChartFrame({className, children}: {className?: string; children: React.ReactNode}) { return <div className={cn(css.frame, chartVarsClassName, className)} data-spectrum-chart="registry-frame">{children}</div>; }
export function ChartPlotSurface({children, className}: {children: React.ReactNode; className?: string}) { return <div className={cn(css.surface, className)}><div aria-hidden className={css.plotDots}/><div className={css.plotInner}>{children}</div></div>; }
export function ChartLegend({items = [SERIES.desktop, SERIES.mobile], className}: {items?: {label: string; color: string}[]; className?: string}) { return <ul className={cn(css.legend, className)}>{items.map((item, index) => <li key={item.label} className={css.legendItem}><span className={cn(css.legendSwatch, css[`legendSwatch${index % 5}`])} />{item.label}</li>)}</ul>; }
type ChartTooltipItem = {type?: string; dataKey?: string | number; name?: string | number; color?: string; value?: number | string};
export function ChartTooltipContent({active, payload, label}: {active?: boolean; payload?: ChartTooltipItem[]; label?: React.ReactNode}) { const reduce = Boolean(useReducedMotion()); if (!active || !payload?.length) return <span className={css.tooltipPlaceholder} aria-hidden />; return <motion.div initial={reduce ? {opacity: 0} : {opacity: 0, transform: 'scale(0.97)'}} animate={reduce ? {opacity: 1} : {opacity: 1, transform: 'scale(1)'}} transition={{duration: 0.16, ease: EASE_OUT}} className={css.tooltip}>{label != null ? <p className={css.tooltipTitle}>{String(label)}</p> : null}<ul className={css.tooltipList}>{payload.filter(item => item.type !== 'none').map(item => <li key={String(item.dataKey ?? item.name)}><span className={css.legendSwatch} /><span>{item.name}</span><strong>{typeof item.value === 'number' ? item.value.toLocaleString() : String(item.value ?? '')}</strong></li>)}</ul></motion.div>; }
export const axisTick = {fill: 'currentColor', fontSize: 11, fontFamily: 'var(--font-mono)'} as const;
export const chartGrid = {vertical: false, stroke: 'currentColor', strokeOpacity: 0.14, strokeDasharray: '3 3'} satisfies Partial<React.ComponentProps<typeof CartesianGrid>>;
export const chartXAxis = {axisLine: false, tickLine: false, tickMargin: 8, tick: axisTick, minTickGap: 8} satisfies Partial<React.ComponentProps<typeof XAxis>>;
export const chartYAxis = {axisLine: false, tickLine: false, tickMargin: 8, tick: axisTick, width: 44} satisfies Partial<React.ComponentProps<typeof YAxis>>;
export function ChartGlowFilter({id}: {id: string}) { return <filter id={id} x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur"/><feColorMatrix in="blur" type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 0.5 0" result="glow"/><feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge></filter>; }

type GrowAxis = {index?: number; x?: number; y?: number; width?: number; height?: number; fill?: string; background?: {x?: number; y?: number; width?: number; height?: number}};
export type GrowBarOptions = {horizontal?: boolean; introStartedAt: number; dataLength: number; reduce?: boolean; radius?: number | [number, number, number, number]; stripped?: boolean; glowId?: string};
function getGrow({index, dataLength, horizontal, introStartedAt, reduce}: {index: number; dataLength: number; horizontal: boolean; introStartedAt: number; reduce: boolean}) { if (reduce || index < 0 || dataLength <= 0) return null; const startMs = index * BAR_STAGGER * 1000; const durationMs = BAR_GROW * 1000; const endMs = startMs + durationMs; const elapsed = Date.now() - introStartedAt; if (elapsed >= endMs) return null; const from = elapsed <= startMs ? 0 : (elapsed - startMs) / durationMs; const axis = horizontal ? 'X' : 'Y'; return {initial: {transform: `scale${axis}(${from})`}, animate: {transform: `scale${axis}(1)`}, transition: {duration: (endMs - Math.max(elapsed, startMs)) / 1000, ease: EASE_OUT, delay: Math.max(0, startMs - elapsed) / 1000}, style: {transformOrigin: horizontal ? 'left center' : 'center bottom'} as React.CSSProperties}; }
export function GrowBar({x = 0, y = 0, width = 0, height = 0, fill, index = 0, background, horizontal = false, introStartedAt, dataLength, reduce = false, radius = 4, stripped = false, glowId}: GrowAxis & GrowBarOptions) { const grow = getGrow({index, dataLength, horizontal, introStartedAt, reduce}); const hit = background ?? {x, y, width, height}; const painted = <Rectangle x={x} y={y} width={Math.max(0, width - (stripped && horizontal ? 3 : 0))} height={Math.max(0, height - (stripped && !horizontal ? 3 : 0))} radius={radius} fill={fill} filter={glowId ? `url(#${glowId})` : undefined}/>; return <g><rect x={hit.x ?? x} y={hit.y ?? y} width={hit.width ?? width} height={hit.height ?? height} fill="transparent"/>{grow ? <motion.g initial={grow.initial} animate={grow.animate} transition={grow.transition}>{painted}</motion.g> : painted}</g>; }
export function createGrowBarShape(options: GrowBarOptions) { function Shape(props: unknown) { return <GrowBar {...(props as GrowAxis)} {...options}/>; } Shape.displayName = 'SpectrumGrowBar'; return Shape; }
export function markOpacity(active: string | number | null, key: string | number) { return active == null || active === key ? 1 : HOVER_OPACITY; }
export function BarFillDefs({id, color, variant}: {id: string; color: string; variant: BarFillVariant}) { return <>{variant === 'hatched' ? <pattern id={`${id}-hatched`} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7" fill={color} opacity={0.16}/><line x1="0" y1="0" x2="0" y2="7" stroke={color} strokeWidth="2.4"/></pattern> : null}{variant === 'gradient' ? <linearGradient id={`${id}-gradient`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color}/><stop offset="100%" stopColor={color} stopOpacity={0.18}/></linearGradient> : null}</>; }
export function barFillUrl(id: string, variant: BarFillVariant, color: string) { return variant === 'default' ? color : `url(#${id}-${variant})`; }
export function ChartLoadingBars({count = 12}: {count?: number}) { const reduce = Boolean(useReducedMotion()); return <div className={css.loading} aria-label="Loading chart">{Array.from({length: count}, (_, index) => <div key={index} className={cn(css.loadingBar, css[`loadingBar${index % 8}`])}/>) }{reduce ? null : <motion.div aria-hidden className={css.loadingSweep} initial={{transform: 'translateX(-120%)'}} animate={{transform: 'translateX(420%)'}} transition={{duration: 1.15, ease: 'linear', repeat: Infinity}}/>}</div>; }
