import { useCallback, useEffect, useState } from "react";

export interface HistoryRow {
  id: string | number;
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

export interface RestoreResult {
  evaluation_id: string;
  data_package: Record<string, unknown>;
  tasks_output: string[];
  reasonings: string[];
  final_output: string;
}

interface LatestResponse {
  history: HistoryRow | null;
  replay_available: boolean;
  result: RestoreResult | null;
}

interface Props {
  onReplay: (result: RestoreResult) => void;
  onBranch: (row: HistoryRow) => void;
  /** Bump to force a refetch (e.g. after a new evaluation completes) */
  refreshKey?: number;
}

function verdictPillClass(verdict: string): string {
  if (verdict === "AUTHORIZE") return "bg-reasoner-green/15 text-reasoner-green";
  if (verdict === "DECLINE") return "bg-reasoner-red/15 text-reasoner-red";
  if (verdict === "MODIFY") return "bg-amber-50 text-amber-700";
  return "bg-reasoner-line/50 text-reasoner-mute";
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const delta = Date.now() - then;
  const mins = Math.round(delta / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

export default function LastSessionReplay({ onReplay, onBranch, refreshKey = 0 }: Props) {
  const [data, setData] = useState<LatestResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch("/api/evaluations/latest");
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json: LatestResponse = await resp.json();
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setErr((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const handleReplay = useCallback(() => {
    if (data?.result) onReplay(data.result);
  }, [data, onReplay]);

  const handleBranch = useCallback(() => {
    if (data?.history) onBranch(data.history);
  }, [data, onBranch]);

  if (err) return null;
  if (!data || !data.history) return null;

  const h = data.history;
  const replayable = data.replay_available;

  return (
    <div className="mt-10">
      <div className="text-[10px] font-mono text-reasoner-mute tracking-[0.14em] mb-3">
        LAST SESSION · REPLAY
      </div>
      <div className="bg-reasoner-paper border border-reasoner-line rounded-xl overflow-hidden">
        <div className="flex items-center gap-4 px-5 py-4">
          <div className="w-12 h-14 rounded bg-reasoner-bg border border-reasoner-line overflow-hidden flex items-center justify-center shrink-0">
            {h.image_path ? (
              <img
                src={`/api/images/${h.image_path.split("/").pop()}`}
                alt=""
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            ) : null}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[15px] font-semibold text-reasoner-ink truncate">
              {h.product_name || "Untitled submission"}
            </div>
            <div className="text-[11.5px] font-mono text-reasoner-mute mt-0.5">
              {h.brand && `${h.brand} · `}
              {h.inferred_category || h.category}
              {h.price ? ` · $${h.price.toFixed(2)}` : ""} · {timeAgo(h.timestamp)}
            </div>
          </div>
          <span
            className={`px-2.5 py-1 rounded text-[11px] font-mono font-bold tracking-[0.08em] ${verdictPillClass(
              h.verdict,
            )}`}
          >
            {h.verdict || "—"} {h.confidence ? `· ${h.confidence}%` : ""}
          </span>
          <button
            type="button"
            onClick={handleReplay}
            disabled={!replayable}
            title={replayable ? "Restore this evaluation instantly" : "Replay unavailable. Start the backend-cached run in this session first."}
            className="px-3.5 py-1.5 text-[13px] font-semibold rounded-md bg-reasoner-ink text-reasoner-paper hover:bg-reasoner-body transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="font-mono mr-1">▶</span>
            Replay reasoning
          </button>
          <button
            type="button"
            onClick={handleBranch}
            className="px-3.5 py-1.5 text-[13px] font-semibold text-reasoner-ink bg-reasoner-paper border border-reasoner-line rounded-md hover:bg-reasoner-bg transition-colors"
          >
            Branch into new run
          </button>
        </div>
      </div>
    </div>
  );
}
