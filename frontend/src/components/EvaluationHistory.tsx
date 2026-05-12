import { useEffect, useState } from "react";

interface Evaluation {
  id: string;
  timestamp: string;
  product_name: string;
  brand: string;
  category: string;
  inferred_category: string;
  price: number;
  claims: string;
  verdict: string;
  confidence: number;
  overlap_classification: string;
  expected_revenue: number;
  max_similarity: number;
  risk_rating: string;
  image_path: string;
}

interface Stats {
  total: number;
  authorize_count: number;
  decline_count: number;
  modify_count: number;
  avg_confidence: number;
}

function verdictColor(verdict: string): string {
  switch (verdict.toUpperCase()) {
    case "AUTHORIZE":
      return "bg-reasoner-green/15 text-reasoner-green";
    case "DECLINE":
      return "bg-red-50 text-reasoner-red";
    case "MODIFY":
      return "bg-amber-50 text-amber-700";
    default:
      return "bg-reasoner-line/50 text-reasoner-mute";
  }
}

function riskColor(risk: string): string {
  switch (risk.toUpperCase()) {
    case "HIGH":
      return "text-reasoner-red";
    case "MEDIUM":
      return "text-amber-700";
    case "LOW":
      return "text-reasoner-green";
    default:
      return "text-reasoner-mute";
  }
}

function formatRevenue(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
  if (val > 0) return `$${val.toFixed(0)}`;
  return "--";
}

function formatDate(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return ts;
  }
}

export default function EvaluationHistory() {
  const [evals, setEvals] = useState<Evaluation[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("ALL");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch("/api/evaluations").then((r) => r.json()),
      fetch("/api/evaluations/stats").then((r) => r.json()),
    ])
      .then(([evalData, statsData]) => {
        setEvals(evalData);
        setStats(statsData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered =
    filter === "ALL" ? evals : evals.filter((e) => e.verdict.toUpperCase() === filter);

  return (
    <div className="flex-1 p-6 bg-reasoner-bg">
      <div className="max-w-[1200px] mx-auto space-y-6">
        {/* Stats cards */}
        {stats && stats.total > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-4">
              <div className="text-2xl font-mono tabular-nums font-bold text-reasoner-ink">{stats.total}</div>
              <div className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em] mt-0.5">Total Evaluations</div>
            </div>
            <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-4">
              <div className="text-2xl font-mono tabular-nums font-bold text-reasoner-green">{stats.authorize_count}</div>
              <div className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em] mt-0.5">Authorized</div>
            </div>
            <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-4">
              <div className="text-2xl font-mono tabular-nums font-bold text-reasoner-red">{stats.decline_count}</div>
              <div className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em] mt-0.5">Declined</div>
            </div>
            <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-4">
              <div className="text-2xl font-mono tabular-nums font-bold text-amber-700">{stats.modify_count}</div>
              <div className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em] mt-0.5">Modify</div>
            </div>
            <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-4">
              <div className="text-2xl font-mono tabular-nums font-bold text-reasoner-ink">{stats.avg_confidence}%</div>
              <div className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em] mt-0.5">Avg Confidence</div>
            </div>
          </div>
        )}

        {/* Filter + table */}
        <div className="bg-reasoner-paper rounded-lg border border-reasoner-line">
          <div className="flex items-center justify-between px-5 py-3 border-b border-reasoner-line">
            <h2 className="text-sm font-semibold text-reasoner-ink">Past Evaluations</h2>
            <div className="flex gap-1">
              {["ALL", "AUTHORIZE", "MODIFY", "DECLINE"].map((v) => (
                <button
                  key={v}
                  onClick={() => setFilter(v)}
                  className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
                    filter === v
                      ? "bg-reasoner-accent text-reasoner-paper"
                      : "bg-reasoner-bg text-reasoner-mute hover:bg-reasoner-line/50"
                  }`}
                >
                  {v === "ALL" ? "All" : v.charAt(0) + v.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-reasoner-mute font-mono">LOADING…</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-sm text-reasoner-mute">
              {evals.length === 0
                ? "No evaluations yet. Submit a product to get started."
                : "No evaluations match this filter."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left border-b border-reasoner-line">
                    <th className="px-5 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Date</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Product</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Category</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Price</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Verdict</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Confidence</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Risk</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Overlap</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Projected Rev</th>
                    <th className="px-3 py-2 font-mono font-semibold text-reasoner-mute text-[10px] uppercase tracking-[0.05em]">Similarity</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((ev) => (
                    <tr key={ev.id} className="border-b border-reasoner-line/60 hover:bg-reasoner-bg">
                      <td className="px-5 py-2.5 text-reasoner-mute font-mono whitespace-nowrap">
                        {formatDate(ev.timestamp)}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="font-medium text-reasoner-ink">{ev.product_name}</div>
                        {ev.brand && <div className="text-reasoner-mute text-[11px]">{ev.brand}</div>}
                      </td>
                      <td className="px-3 py-2.5 text-reasoner-body">
                        <div>{ev.inferred_category || ev.category}</div>
                        {ev.inferred_category && ev.inferred_category !== ev.category && (
                          <div className="text-[10px] text-reasoner-dim font-mono">was: {ev.category}</div>
                        )}
                      </td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-reasoner-ink">${ev.price.toFixed(2)}</td>
                      <td className="px-3 py-2.5">
                        {ev.verdict ? (
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold tracking-[0.05em] ${verdictColor(ev.verdict)}`}
                          >
                            {ev.verdict}
                          </span>
                        ) : (
                          <span className="text-reasoner-dim">--</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        {ev.confidence > 0 ? (
                          <div className="flex items-center gap-1.5">
                            <div className="w-12 h-1.5 bg-reasoner-line/50 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-reasoner-accent rounded-full"
                                style={{ width: `${ev.confidence}%` }}
                              />
                            </div>
                            <span className="font-mono tabular-nums text-reasoner-body">{ev.confidence}%</span>
                          </div>
                        ) : (
                          <span className="text-reasoner-dim">--</span>
                        )}
                      </td>
                      <td className={`px-3 py-2.5 font-mono font-medium tracking-[0.05em] ${riskColor(ev.risk_rating)}`}>
                        {ev.risk_rating || "--"}
                      </td>
                      <td className="px-3 py-2.5 text-reasoner-body">
                        {ev.overlap_classification || "--"}
                      </td>
                      <td className="px-3 py-2.5 font-mono tabular-nums font-medium text-reasoner-ink">
                        {formatRevenue(ev.expected_revenue)}
                      </td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-reasoner-body">
                        {ev.max_similarity > 0 ? `${(ev.max_similarity * 100).toFixed(0)}%` : "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
