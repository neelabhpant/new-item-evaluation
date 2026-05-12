interface Props {
  matrix: number[][];
  names: string[];
}

function cellColor(score: number, isDiagonal: boolean): string {
  if (isDiagonal) return "bg-reasoner-line/40 text-reasoner-dim";
  if (score >= 0.9) return "bg-red-200 text-red-900";
  if (score >= 0.8) return "bg-red-50 text-reasoner-red";
  if (score >= 0.7) return "bg-amber-100 text-amber-800";
  if (score >= 0.5) return "bg-amber-50 text-amber-700";
  return "bg-emerald-50 text-reasoner-green";
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

export default function PortfolioMatrix({ matrix, names }: Props) {
  if (matrix.length < 2) return null;

  // Find the highest off-diagonal similarity
  let maxOffDiag = 0;
  let maxPair: [number, number] = [0, 1];
  for (let i = 0; i < matrix.length; i++) {
    for (let j = i + 1; j < matrix.length; j++) {
      if (matrix[i][j] > maxOffDiag) {
        maxOffDiag = matrix[i][j];
        maxPair = [i, j];
      }
    }
  }

  return (
    <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-reasoner-ink">Portfolio Similarity Matrix</h3>
          <p className="text-xs text-reasoner-mute mt-0.5">
            Pairwise CLIP similarity between submitted products. High values indicate intra-portfolio cannibalization risk.
          </p>
        </div>
        {maxOffDiag >= 0.8 && (
          <div className="px-3 py-1.5 bg-red-50 border border-red-200 rounded text-xs text-reasoner-red">
            <span className="font-mono tabular-nums font-semibold">{(maxOffDiag * 100).toFixed(0)}%</span>{" "}
            similar: {truncate(names[maxPair[0]], 20)} ↔ {truncate(names[maxPair[1]], 20)}
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1.5" />
              {names.map((n, i) => (
                <th
                  key={i}
                  className="px-2 py-1.5 font-medium text-reasoner-body max-w-[100px] truncate text-center"
                  title={n}
                >
                  {truncate(n, 15)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => (
              <tr key={i}>
                <td className="px-2 py-1.5 font-medium text-reasoner-body max-w-[120px] truncate" title={names[i]}>
                  {truncate(names[i], 18)}
                </td>
                {row.map((val, j) => (
                  <td
                    key={j}
                    className={`px-3 py-1.5 text-center font-mono tabular-nums rounded ${cellColor(val, i === j)}`}
                  >
                    {i === j ? "--" : `${(val * 100).toFixed(0)}%`}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-3 text-[10px] font-mono text-reasoner-mute tracking-[0.05em]">
        <span>LEGEND:</span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-200" /> High (&gt;90%)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-50" /> Elevated (&gt;80%)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-amber-100" /> Moderate (&gt;70%)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-emerald-50 border border-emerald-200" /> Low (&lt;50%)
        </span>
      </div>
    </div>
  );
}
