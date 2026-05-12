import type { StepState } from "../types";
import ArtifactCard from "./reasoner/ArtifactCard";
import Cite from "./reasoner/Cite";
import { elapsedLabel } from "../hooks/useEvaluationSocket";

interface Props {
  step: StepState | undefined;
}

function strip(text: string): string {
  return text.replace(/\*\*/g, "");
}

function extractCategory(output: string): string {
  const labeled = output.match(/^CATEGORY:\s*(.+)/im);
  if (labeled) return strip(labeled[1].trim());
  const match = output.match(/(?:category)[:\s]*["']?([^"'\n,]+)/i);
  return match ? strip(match[1].trim()) : "";
}

function extractGrowth(output: string): string {
  const labeled = output.match(/CATEGORY_GROWTH:\s*([+-]?\d+\.?\d*)%?\s*/i);
  if (labeled) return labeled[1];
  const match = output.match(/(\d+\.?\d*)%?\s*(?:yoy|year.over.year|YoY)/i)
    || output.match(/(?:yoy|year.over.year|growth)[:\s]*([+-]?\d+\.?\d*%?)/i);
  return match ? match[1].replace(/%$/, "") : "";
}

function extractTiming(output: string): string {
  const labeled = output.match(/MARKET_TIMING:\s*(Early|On-Trend|On Trend|Late)/i);
  if (labeled) return strip(labeled[1].trim());
  if (/\bon[- ]trend\b/i.test(output)) return "On-Trend";
  if (/\bearly\b/i.test(output)) return "Early";
  if (/\blate\b/i.test(output)) return "Late";
  return "";
}

function extractTopTrend(output: string): string {
  const labeled = output.match(/TOP_TREND:\s*([^\n]+)/i);
  if (labeled) return strip(labeled[1].trim());
  const match = output.match(/(?:top trend|trending|key trend)[:\s]*["']?([^"'\n]+)/i);
  return match ? strip(match[1].trim()) : "";
}

function timingColor(timing: string): string {
  if (/on.trend/i.test(timing)) return "bg-emerald-50 text-reasoner-green border-emerald-200";
  if (/early/i.test(timing)) return "bg-reasoner-cyan/10 text-reasoner-cyan border-reasoner-cyan/30";
  return "bg-amber-50 text-amber-700 border-amber-200";
}

export default function MarketContext({ step }: Props) {
  if (!step || step.status === "pending") return null;

  const status = step.status === "error" ? "error" : step.status === "running" ? "running" : "done";
  const tone = step.status === "running" ? "running" : "default";

  if (step.status === "running") {
    return (
      <ArtifactCard agent="▸ MARKET CONTEXT" status={status} tone={tone} title="Market Context">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-reasoner-line/50 rounded w-2/3" />
          <div className="h-6 bg-reasoner-line/50 rounded w-full" />
          <div className="h-4 bg-reasoner-line/50 rounded w-1/2" />
        </div>
      </ArtifactCard>
    );
  }

  const raw = step.output ? strip(step.output) : "";
  const category = raw ? extractCategory(raw) : "";
  const growth = raw ? extractGrowth(raw) : "";
  const timing = raw ? extractTiming(raw) : "";
  const topTrend = raw ? extractTopTrend(raw) : "";

  const summary = [
    category,
    growth && `growing ${growth}% YoY`,
    timing,
  ].filter(Boolean).join(" · ") || "Category context";

  return (
    <ArtifactCard
      agent="▸ MARKET CONTEXT"
      status={status}
      elapsed={elapsedLabel(step)}
      title="Category & Market Timing"
      summary={summary}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {category && (
          <div>
            <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Category</span>
            <p className="text-sm font-semibold text-reasoner-ink mt-0.5">{category}</p>
          </div>
        )}
        {growth && (
          <div>
            <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">YoY Growth</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <svg className="w-3.5 h-3.5 text-reasoner-green" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
              <Cite
                index={1}
                source={{
                  source: "category_benchmarks.yoy_growth",
                  description: `DuckDB category benchmark. Year-over-year growth rate for ${category || "the category"} across the catalog.`,
                  value: `+${growth}%`,
                }}
              >
                <span className="text-sm font-mono tabular-nums font-semibold text-reasoner-green">
                  growing {growth}%
                </span>
              </Cite>
            </div>
          </div>
        )}
        {timing && (
          <div>
            <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Market Timing</span>
            <div className="mt-0.5">
              <Cite
                index={2}
                source={{
                  source: "risk_agent.assess_timing()",
                  description:
                    "Early = ahead of the trend curve; On-Trend = actively growing segment; Late = plateauing or declining.",
                  value: timing,
                }}
              >
                <span className={`text-[10px] font-mono font-semibold px-2.5 py-0.5 rounded-full border tracking-[0.05em] ${timingColor(timing)}`}>
                  {timing}
                </span>
              </Cite>
            </div>
          </div>
        )}
        {topTrend && (
          <div>
            <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Top Trend</span>
            <p className="text-xs font-medium text-reasoner-ink mt-0.5 leading-snug">{topTrend}</p>
          </div>
        )}
      </div>
    </ArtifactCard>
  );
}
