import { cn } from "@/lib/utils";

/** Mini inline sparkline trend chart. Pure SVG, no dependencies. */
export function TrendSparkline({
  points,
  height = 20,
  color = "var(--color-accent)",
  className,
}: {
  points: number[];
  height?: number;
  color?: string;
  className?: string;
}) {
  if (points.length < 2) return null;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const xStep = 100 / (points.length - 1);
  const path = points
    .map((p, i) => {
      const x = xStep * i;
      const y = 100 - ((p - min) / range) * 100;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");
  return (
    <svg
      className={cn("w-full h-auto block shrink-0", className)}
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
