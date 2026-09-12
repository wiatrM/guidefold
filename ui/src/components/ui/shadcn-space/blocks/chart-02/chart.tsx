// Adapted from shadcn-space chart-02 (MIT). Source: https://shadcnspace.com/r/chart-02.json
// (qa/spectrum-registry.json carries the review hash). Guidefold adaptation (2026-09-12):
// a real segment list with a real total in the centre (no "$27,850" demo figure), a real
// growth badge only when one is supplied, and no fabricated growth otherwise. The legend
// swatch takes a Tailwind class (not an inline style) so no dynamic `style=` attribute is
// needed here. `w-full max-w-50` (kept alongside the original `mx-auto aspect-square
// max-h-50`): inside a `flex-col` ancestor, `mx-auto` alone makes a flex item shrink-to-fit
// instead of stretching, and with `aspect-ratio` depending on a not-yet-measured recharts
// SVG for its intrinsic width, the two together deadlocked at 0x0 (recharts warned "width(0)
// and height(0)"). An explicit width breaks the deadlock; `max-w-50` keeps it square-ish.
'use client';
import {Label, Pie, PieChart} from 'recharts';
import {Card, CardHeader, CardTitle, CardContent} from '@/components/ui/card';
import {ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig} from '@/components/ui/chart';
import {cn} from '@/lib/utils';

export interface DonutSegment { key: string; label: string; value: number; fill: string; swatchClass: string }

export function DonutChart({title, eyebrow, centerLabel, centerValue, segments}: {title?: string; eyebrow?: string; centerLabel: string; centerValue: string; segments: DonutSegment[]}) {
  const config = Object.fromEntries(segments.map(s => [s.key, {label: s.label, color: s.fill}])) satisfies ChartConfig;
  const data = segments.map(s => ({...s, name: s.label}));
  return <Card className="h-full w-full gap-6 rounded-xl border py-6 shadow-xs">
    {title && <CardHeader className="px-6">
      <CardTitle className="text-lg font-medium">{title}</CardTitle>
      {eyebrow && <p className="text-xs text-muted-foreground">{eyebrow}</p>}
    </CardHeader>}
    <CardContent className="flex flex-1 flex-col justify-between gap-6 px-6">
      <ChartContainer config={config} className="mx-auto aspect-square max-h-50 w-full max-w-50" role="img" aria-label={(title ?? centerLabel) + ' out of ' + centerValue + ': ' + segments.map(s => s.label + ' ' + s.value).join(', ')}>
        <PieChart margin={{top: -10}}>
          <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} strokeWidth={4}>
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any -- recharts' LabelProps viewBox union has no shared cx/cy without a manual guard */}
            <Label content={(props: any) => {
              const viewBox = props.viewBox as {cx?: number; cy?: number} | undefined;
              if (!viewBox || viewBox.cx === undefined || viewBox.cy === undefined) return null;
              return <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                <tspan x={viewBox.cx} y={viewBox.cy - 10} className="fill-muted-foreground text-sm">{centerLabel}</tspan>
                <tspan x={viewBox.cx} y={viewBox.cy + 15} className="fill-foreground text-xl font-medium">{centerValue}</tspan>
              </text>;
            }} />
          </Pie>
        </PieChart>
      </ChartContainer>
      <ul className="flex flex-col gap-3">
        {segments.map(segment => <li key={segment.key} className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <span className={cn('h-4 w-1 shrink-0 rounded-full', segment.swatchClass)} aria-hidden="true" />
            <span className="truncate text-sm font-normal">{segment.label}</span>
          </span>
          <strong className="text-sm font-medium tabular-nums">{segment.value}</strong>
        </li>)}
      </ul>
    </CardContent>
  </Card>;
}
