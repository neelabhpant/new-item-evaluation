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

function verdictBadge(verdict: string) {
  const upper = verdict.toUpperCase();
  const cls =
    upper === "AUTHORIZE"
      ? "bg-reasoner-green/15 text-reasoner-green border-reasoner-green/30"
      : upper === "DECLINE"
      ? "bg-red-50 text-reasoner-red border-red-200"
      : upper === "MODIFY"
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-reasoner-line/50 text-reasoner-mute border-reasoner-line";
  return (
    <span className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold border tracking-[0.05em] ${cls}`}>
      {upper || "PENDING"}
    </span>
  );
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
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return ts;
  }
}

export default function MerchantQueue() {
  const [evals, setEvals] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("ALL");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"confidence" | "revenue" | "date">("confidence");

  useEffect(() => {
    fetch("/api/evaluations?limit=100")
      .then((r) => r.json())
      .then(setEvals)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered =
    filter === "ALL" ? evals : evals.filter((e) => e.verdict.toUpperCase() === filter);

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === "confidence") return b.confidence - a.confidence;
    if (sortBy === "revenue") return b.expected_revenue - a.expected_revenue;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  return (
    <div className="flex-1 p-6 bg-reasoner-bg">
      <div className="max-w-[1100px] mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-reasoner-ink">Merchant Review Queue</h2>
            <p className="text-xs text-reasoner-mute mt-0.5">
              Review and act on evaluated product submissions
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-1">
              {(["confidence", "revenue", "date"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setSortBy(s)}
                  className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                    sortBy === s
                      ? "bg-reasoner-ink text-reasoner-paper"
                      : "bg-reasoner-bg text-reasoner-mute hover:bg-reasoner-line/50"
                  }`}
                >
                  {s === "confidence" ? "By Confidence" : s === "revenue" ? "By Revenue" : "By Date"}
                </button>
              ))}
            </div>
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
                  {v === "ALL" ? `All (${evals.length})` : v.charAt(0) + v.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-8 text-center text-sm text-reasoner-mute font-mono">
            LOADING QUEUE…
          </div>
        ) : sorted.length === 0 ? (
          <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-8 text-center text-sm text-reasoner-mute">
            No submissions in queue.
          </div>
        ) : (
          <div className="space-y-2">
            {sorted.map((ev) => (
              <div
                key={ev.id}
                className="bg-reasoner-paper rounded-lg border border-reasoner-line hover:border-reasoner-accent/60 transition-colors"
              >
                <div
                  className="flex items-center gap-4 px-5 py-3 cursor-pointer"
                  onClick={() => setExpanded(expanded === ev.id ? null : ev.id)}
                >
                  {/* Product info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-reasoner-ink truncate">
                        {ev.product_name}
                      </span>
                      <span className="text-xs text-reasoner-mute">{ev.brand}</span>
                    </div>
                    <div className="text-xs text-reasoner-mute font-mono mt-0.5">
                      {ev.inferred_category || ev.category} · ${ev.price.toFixed(2)}
                    </div>
                  </div>

                  {/* Verdict */}
                  <div className="shrink-0">{verdictBadge(ev.verdict)}</div>

                  {/* Confidence bar */}
                  <div className="w-28 shrink-0">
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 h-2 bg-reasoner-line/50 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            ev.confidence >= 80
                              ? "bg-reasoner-green"
                              : ev.confidence >= 60
                              ? "bg-amber-500"
                              : "bg-reasoner-red"
                          }`}
                          style={{ width: `${ev.confidence}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono tabular-nums font-medium text-reasoner-body w-8 text-right">
                        {ev.confidence > 0 ? `${ev.confidence}%` : "--"}
                      </span>
                    </div>
                  </div>

                  {/* Revenue */}
                  <div className="w-20 text-right shrink-0">
                    <div className="text-sm font-mono tabular-nums font-semibold text-reasoner-ink">
                      {formatRevenue(ev.expected_revenue)}
                    </div>
                    <div className="text-[10px] font-mono text-reasoner-mute">projected</div>
                  </div>

                  {/* Date */}
                  <div className="w-16 text-right text-xs font-mono text-reasoner-mute shrink-0">
                    {formatDate(ev.timestamp)}
                  </div>

                  {/* Expand icon */}
                  <svg
                    className={`w-4 h-4 text-reasoner-dim transition-transform ${
                      expanded === ev.id ? "rotate-180" : ""
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>

                {/* Expanded detail */}
                {expanded === ev.id && (
                  <div className="px-5 pb-4 pt-1 border-t border-reasoner-line">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                      <div>
                        <div className="text-[10px] font-mono text-reasoner-mute tracking-[0.1em] uppercase mb-0.5">Overlap</div>
                        <div className="font-medium text-reasoner-ink">
                          {ev.overlap_classification || "--"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono text-reasoner-mute tracking-[0.1em] uppercase mb-0.5">Max Similarity</div>
                        <div className="font-mono tabular-nums font-medium text-reasoner-ink">
                          {ev.max_similarity > 0
                            ? `${(ev.max_similarity * 100).toFixed(0)}%`
                            : "--"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono text-reasoner-mute tracking-[0.1em] uppercase mb-0.5">Risk Rating</div>
                        <div
                          className={`font-mono font-medium tracking-[0.05em] ${
                            ev.risk_rating === "HIGH"
                              ? "text-reasoner-red"
                              : ev.risk_rating === "MEDIUM"
                              ? "text-amber-700"
                              : "text-reasoner-green"
                          }`}
                        >
                          {ev.risk_rating || "--"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono text-reasoner-mute tracking-[0.1em] uppercase mb-0.5">Claims</div>
                        <div className="font-medium text-reasoner-ink">{ev.claims || "--"}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
