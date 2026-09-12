// Adapted from shadcn-space chart-01 (MIT). Source: https://shadcnspace.com/r/chart-01.json
// (qa/spectrum-registry.json carries the review hash). Guidefold adaptation (2026-09-12):
// one honest series (no fabricated "profit"/"expense" stack), real category/value pairs
// and no fake "+18% than last year" badge — the header shows only counts the API returned.
'use client';
import {Card, CardHeader, CardTitle, CardContent} from '@/components/ui/card';
import {ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig} from '@/components/ui/chart';
import {Bar, BarChart, CartesianGrid, XAxis, YAxis} from 'recharts';

export interface FunnelPoint { category: string; value: number }

const chartConfig = {value: {label: 'Count', color: 'var(--chart-2)'}} satisfies ChartConfig;

export function FunnelBarChart({title, eyebrow, data}: {title: string; eyebrow: string; data: FunnelPoint[]}) {
  return <Card className="w-full gap-6 rounded-xl border py-6 shadow-xs">
    <CardHeader className="gap-1 px-6">
      <CardTitle className="text-lg font-medium">{title}</CardTitle>
      <p className="text-xs text-muted-foreground">{eyebrow}</p>
    </CardHeader>
    <CardContent className="px-6">
      <ChartContainer config={chartConfig} className="h-75 w-full" role="img" aria-label={title + ': ' + data.map(d => d.category + ' ' + d.value).join(', ')}>
        <BarChart accessibilityLayer data={data} margin={{left: -20}}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="category" tickLine={false} tickMargin={10} axisLine={false} fontSize={12} />
          <YAxis tickLine={false} axisLine={false} tickMargin={10} fontSize={12} allowDecimals={false} />
          <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel indicator="line" />} />
          <Bar dataKey="value" fill="var(--color-value)" radius={[4, 4, 0, 0]} barSize={36} />
        </BarChart>
      </ChartContainer>
    </CardContent>
  </Card>;
}
