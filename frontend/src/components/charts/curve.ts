/**
 * Smooth SVG paths for line charts: a monotone cubic (Fritsch–Carlson). The curve passes through every point and
 * never overshoots between two of them, so a flat run stays flat and a zero never dips below the axis — the smooth
 * look without misreporting the data. Points are [x, y] in SVG coordinates with x increasing.
 */
export type Point = readonly [number, number];

const f = (n: number) => n.toFixed(1);

/** Path commands for one run of points, starting with "M". */
export function smoothPath(points: readonly Point[]): string {
  const n = points.length;
  if (n === 0) return "";
  if (n === 1) return `M${f(points[0][0])} ${f(points[0][1])}`;
  if (n === 2) return `M${f(points[0][0])} ${f(points[0][1])} L${f(points[1][0])} ${f(points[1][1])}`;

  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(points[i + 1][0] - points[i][0]);
    slope.push(dx[i] === 0 ? 0 : (points[i + 1][1] - points[i][1]) / dx[i]);
  }
  // Tangents: average of neighbouring slopes, zero at a peak/valley or where either side is flat.
  const m: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i++) m.push(slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2);
  m.push(slope[n - 2]);
  // Fritsch–Carlson limit keeps each segment monotone.
  for (let i = 0; i < n - 1; i++) {
    if (slope[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / slope[i];
    const b = m[i + 1] / slope[i];
    const h = a * a + b * b;
    if (h > 9) {
      const t = 3 / Math.sqrt(h);
      m[i] = t * a * slope[i];
      m[i + 1] = t * b * slope[i];
    }
  }

  let d = `M${f(points[0][0])} ${f(points[0][1])}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = points[i];
    const [x1, y1] = points[i + 1];
    const h = dx[i] / 3;
    d += ` C${f(x0 + h)} ${f(y0 + m[i] * h)} ${f(x1 - h)} ${f(y1 - m[i + 1] * h)} ${f(x1)} ${f(y1)}`;
  }
  return d;
}
