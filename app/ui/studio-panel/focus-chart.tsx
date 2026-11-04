'use client';

import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  XAxis,
  ResponsiveContainer,
} from 'recharts';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';

interface FocusChartProps {
  focusHistory: { score: number; timestamp: number }[];
}

const chartConfig = {
  attention: {
    label: 'Focus',
    color: 'hsl(215, 100%, 60%)',
    icon: Activity,
  },
} satisfies ChartConfig;

export default function FocusChart({ focusHistory }: FocusChartProps) {
  // Convert history to chart data with time labels
  const chartData = focusHistory
    .filter((_, i) => i % 3 === 0) // Sample every 3rd point to avoid overcrowding
    .map((entry) => ({
      time: new Date(entry.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
      attention: entry.score,
    }));

  // Calculate stats
  const scores = focusHistory.map((h) => h.score);
  const avgScore =
    scores.length > 0
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : 0;

  // Trend: compare first half to second half
  let trendPercentage = 0;
  let isTrendingUp = true;
  if (scores.length >= 6) {
    const half = Math.floor(scores.length / 2);
    const firstHalf = scores.slice(0, half);
    const secondHalf = scores.slice(half);
    const firstAvg =
      firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
    const secondAvg =
      secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;
    if (firstAvg > 0) {
      trendPercentage = Math.round(
        ((secondAvg - firstAvg) / firstAvg) * 100
      );
      isTrendingUp = trendPercentage >= 0;
    }
  }

  const hasData = chartData.length > 2;

  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Activity className="h-4 w-4" /> Session Focus
        </CardTitle>
        <CardDescription className="text-xs">
          {hasData
            ? 'Your focus level this session'
            : 'Focus data will appear once tracking starts'}
        </CardDescription>
      </CardHeader>
      <CardContent className="pb-2">
        {hasData ? (
          <ChartContainer config={chartConfig} className="h-[120px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ left: 0, right: 0, top: 5, bottom: 5 }}
              >
                <CartesianGrid vertical={false} opacity={0.2} />
                <XAxis
                  dataKey="time"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={5}
                  minTickGap={15}
                  tick={{ fontSize: 10 }}
                />
                <ChartTooltip
                  cursor={false}
                  content={<ChartTooltipContent hideLabel />}
                />
                <Area
                  dataKey="attention"
                  type="monotone"
                  fill="var(--color-attention)"
                  fillOpacity={0.3}
                  stroke="var(--color-attention)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartContainer>
        ) : (
          <div className="h-[120px] flex items-center justify-center text-sm text-gray-400">
            Start your camera to see focus data
          </div>
        )}
      </CardContent>
      {hasData && (
        <CardFooter className="pt-0">
          <div className="flex w-full items-center justify-between text-xs">
            <div className="font-medium">Avg: {avgScore}%</div>
            {scores.length >= 6 && (
              <div
                className={`flex items-center gap-1 ${
                  isTrendingUp ? 'text-green-600' : 'text-amber-600'
                }`}
              >
                {isTrendingUp ? (
                  <>
                    Trending up {Math.abs(trendPercentage)}%
                    <TrendingUp className="h-3 w-3" />
                  </>
                ) : (
                  <>
                    Trending down {Math.abs(trendPercentage)}%
                    <TrendingDown className="h-3 w-3" />
                  </>
                )}
              </div>
            )}
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
