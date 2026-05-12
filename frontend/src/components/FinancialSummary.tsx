import { useMemo, useState } from "react";
import type { StepState, EnrichedProduct } from "../types";
import PriceExplorer from "./PriceExplorer";
import ArtifactCard from "./reasoner/ArtifactCard";
import Cite from "./reasoner/Cite";
import { elapsedLabel } from "../hooks/useEvaluationSocket";

interface Props {
  step: StepState | undefined;
  submittedPrice?: number;
  competitorPrices?: number[];
  recommendationOutput?: string;
  enrichedProducts?: EnrichedProduct[];
}

function strip(text: string): string {
  return text.replace(/\*\*/g, "");
}

function extractScenarios(output: string): { label: string; value: string; raw: number }[] {
  const scenarios: { label: string; value: string; raw: number }[] = [];

  const parseAmount = (s: string): number => {
    const clean = s.replace(/[$,\s]/g, "").toLowerCase();
    const m = clean.match(/^([\d.]+)([kmb]?)/);
    if (!m) return 0;
    const n = parseFloat(m[1]);
    if (m[2] === "k") return n * 1_000;
    if (m[2] === "m") return n * 1_000_000;
    if (m[2] === "b") return n * 1_000_000_000;
    return n;
  };

  const bestLabeled = output.match(/BEST_CASE:\s*\$?([\d,.]+\s*(?:million|thousand|[MKB])?)/i);
  const expectedLabeled = output.match(/EXPECTED:\s*\$?([\d,.]+\s*(?:million|thousand|[MKB])?)/i);
  const worstLabeled = output.match(/WORST_CASE:\s*\$?([\d,.]+\s*(?:million|thousand|[MKB])?)/i);

  if (bestLabeled) scenarios.push({ label: "Best case", value: `$${bestLabeled[1].trim()}`, raw: parseAmount(bestLabeled[1]) });
  if (expectedLabeled) scenarios.push({ label: "Expected", value: `$${expectedLabeled[1].trim()}`, raw: parseAmount(expectedLabeled[1]) });
  if (worstLabeled) scenarios.push({ label: "Worst", value: `$${worstLabeled[1].trim()}`, raw: parseAmount(worstLabeled[1]) });
  return scenarios;
}

function extractMargin(output: string): string {
  const labeled = output.match(/^MARGIN:\s*(\d+\.?\d*%?)/im);
  if (labeled) return labeled[1].includes("%") ? labeled[1] : `${labeled[1]}%`;
  const match = output.match(/margin[:\s]*(\d+\.?\d*%?)/i);
  return match ? (match[1].includes("%") ? match[1] : `${match[1]}%`) : "";
}

function extractVendorNote(output: string): string {
  const labeled = output.match(/VENDOR_RELIABILITY:\s*([^\n]+)/i);
  if (labeled) return strip(labeled[1].trim());
  const match = output.match(/vendor\s*(?:reliability|note|assessment)[:\s]*([^\n]+)/i);
  return match ? strip(match[1].trim()) : "";
}

function extractRampAssumption(output: string): string {
  const m = output.match(/RAMP_ASSUMPTION:\s*([^\n]+)/i);
  return m ? strip(m[1].trim()) : "";
}

function isWhiteSpace(output: string): boolean {
  return /RAMP_ASSUMPTION:/i.test(output) || /100%\s*incremental/i.test(output);
}

interface VendorImpact {
  vendor: string;
  tier: string;
  detail: string;
}

function extractVendorImpacts(output: string): VendorImpact[] {
  const impacts: VendorImpact[] = [];
  const section = output.match(/VENDOR_IMPACT:\s*\n([\s\S]*?)(?=\n[A-Z_]+:|$)/);
  if (!section) return impacts;
  const lines = section[1].split("\n").filter((l) => l.trim().startsWith("-"));
  for (const line of lines) {
    if (/NONE/i.test(line)) continue;
    const m = line.match(/^-\s*(.+?)\s*\((\w+)\):\s*(.*)/);
    if (m) {
      impacts.push({ vendor: m[1].trim(), tier: m[2].trim(), detail: m[3].trim() });
    }
  }
  return impacts;
}

function tierBadgeColor(tier: string): string {
  if (tier === "Strategic") return "bg-reasoner-cyan/15 text-reasoner-cyan";
  if (tier === "Preferred") return "bg-reasoner-green/15 text-reasoner-green";
  if (tier === "Probationary") return "bg-red-50 text-reasoner-red";
  return "bg-reasoner-line/50 text-reasoner-mute";
}

interface Scenario {
  replaced: number;
  newRev: number;
  net: number;
  vendorNote: string;
}

const NEW_REV_SCALE: Record<number, number> = { 2: 0.73, 3: 1.0, 4: 1.15, 5: 1.25 };

function computeScenarios(
  enriched: EnrichedProduct[],
  baselineNewRev: number,
): { scenarios: Record<number, Scenario>; availableNs: number[] } {
  const decliners = enriched
    .filter((p) => p.trend === "declining" || p.yoy_growth < 0)
    .sort(
      (a, b) =>
        b.similarity_score * b.annual_revenue - a.similarity_score * a.annual_revenue,
    );

  const scenarios: Record<number, Scenario> = {};
  if (decliners.length === 0 || baselineNewRev <= 0) {
    return { scenarios, availableNs: [] };
  }
  const maxN = Math.min(5, Math.max(2, decliners.length));
  const availableNs: number[] = [];

  for (let n = 2; n <= maxN; n++) {
    const topN = decliners.slice(0, n);
    const replaced = topN.reduce(
      (sum, p) => sum + (p.annual_revenue * Math.abs(p.yoy_growth)) / 100,
      0,
    );
    const newRev = baselineNewRev * (NEW_REV_SCALE[n] ?? 1);
    const net = newRev - replaced;

    const vendorCounts = new Map<string, number>();
    for (const p of topN) {
      vendorCounts.set(p.brand, (vendorCounts.get(p.brand) ?? 0) + 1);
    }
    const vendorNote = Array.from(vendorCounts.entries())
      .map(([v, c]) => `${v} −${c}`)
      .join(" · ");

    scenarios[n] = { replaced, newRev, net, vendorNote };
    availableNs.push(n);
  }
  return { scenarios, availableNs };
}

function fmtK(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${Math.round(value)}`;
}

function fmtDelta(value: number): string {
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${fmtK(Math.abs(value))}`;
}

export default function FinancialSummary({
  step,
  submittedPrice,
  competitorPrices = [],
  recommendationOutput,
  enrichedProducts = [],
}: Props) {
  // Hooks must run unconditionally on every render (Rules of Hooks).
  // Compute parse outputs first so `useMemo` has stable inputs whether the
  // step is pending, running, or complete.
  const [replaceCount, setReplaceCount] = useState<number>(3);

  const raw = step?.output ? strip(step.output) : "";
  const scenarios = raw ? extractScenarios(raw) : [];
  const margin = raw ? extractMargin(raw) : "";
  const vendorNote = raw ? extractVendorNote(raw) : "";
  const whiteSpace = raw ? isWhiteSpace(raw) : false;
  const vendorImpacts = raw && !whiteSpace ? extractVendorImpacts(raw) : [];
  const rampAssumption = raw && whiteSpace ? extractRampAssumption(raw) : "";

  const expectedScenario = scenarios.find((s) => s.label === "Expected");
  const baselineNewRev = expectedScenario?.raw ?? 0;

  const scenarioData = useMemo(
    () => computeScenarios(enrichedProducts, baselineNewRev),
    [enrichedProducts, baselineNewRev],
  );

  // Early returns after all hooks have been registered.
  if (!step || step.status === "pending") return null;

  const status = step.status === "error" ? "error" : step.status === "running" ? "running" : "done";
  const tone = step.status === "running" ? "running" : "default";

  if (step.status === "running") {
    return (
      <ArtifactCard agent="▸ FINANCIAL PROJECTOR" status={status} tone={tone} title="Financial Projection">
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-reasoner-line/50 rounded w-3/4" />
          <div className="h-4 bg-reasoner-line/50 rounded w-1/2" />
          <div className="h-4 bg-reasoner-line/50 rounded w-2/3" />
        </div>
      </ArtifactCard>
    );
  }

  const hasReplacementUI =
    !whiteSpace && scenarioData.availableNs.length > 0 && baselineNewRev > 0;
  const activeN = hasReplacementUI
    ? scenarioData.availableNs.includes(replaceCount)
      ? replaceCount
      : scenarioData.availableNs.includes(3)
        ? 3
        : scenarioData.availableNs[scenarioData.availableNs.length - 1]
    : 0;
  const active: Scenario | null = hasReplacementUI ? scenarioData.scenarios[activeN] : null;

  const finSummary = [
    expectedScenario && `Expected ${expectedScenario.value}`,
    margin && `${margin} margin`,
    active && `net ${fmtDelta(active.net)}`,
  ].filter(Boolean).join(" · ") || "Year 1 projection ready";

  return (
    <ArtifactCard
      agent="▸ FINANCIAL PROJECTOR"
      status={status}
      elapsed={elapsedLabel(step)}
      title="Year 1 Financial Projection"
      summary={finSummary}
      anchorId="fin-artifact"
    >
      {scenarios.length > 0 ? (
        <div className="space-y-2 mb-4">
          {scenarios.map((s) => {
            const isExpected = s.label === "Expected";
            const valueNode = (
              <span className="font-mono tabular-nums font-semibold text-reasoner-ink">
                {s.value} revenue
              </span>
            );
            return (
              <div key={s.label} className="flex items-center justify-between text-xs">
                <span className="text-reasoner-mute">{s.label}</span>
                {isExpected ? (
                  <Cite
                    index={1}
                    source={{
                      source: "financial_agent.project_y1()",
                      description:
                        "Expected Year 1 revenue = median weekly units from comparable products × submitted price × 52, adjusted down 20–30% for new market entry.",
                      value: s.value,
                      formula: "weekly_units × price × 52 × new_entry_adj",
                    }}
                  >
                    {valueNode}
                  </Cite>
                ) : (
                  valueNode
                )}
              </div>
            );
          })}
          {margin && (
            <div className="flex items-center justify-between text-xs pt-2 border-t border-reasoner-line">
              <span className="text-reasoner-mute">Margin</span>
              <Cite
                index={2}
                source={{
                  source: "category_benchmarks.avg_margin",
                  description:
                    "Category-average margin from DuckDB. Used as a proxy for the new product's expected gross margin at retail.",
                  value: margin,
                }}
              >
                <span className="font-mono tabular-nums font-semibold text-reasoner-ink">{margin}</span>
              </Cite>
            </div>
          )}
        </div>
      ) : raw ? (
        <div className="text-xs text-reasoner-body whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto mb-4 font-mono">
          {raw.slice(0, 1500)}
        </div>
      ) : null}

      {whiteSpace && (
        <div className="bg-reasoner-cyan/10 border border-reasoner-cyan/30 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-reasoner-cyan text-reasoner-paper tracking-[0.08em]">
              NEW CATEGORY
            </span>
            <span className="text-xs font-semibold text-reasoner-cyan">100% incremental revenue</span>
          </div>
          <p className="text-xs text-reasoner-body">No cannibalization. All projected revenue is net-new to the retailer.</p>
          {rampAssumption && (
            <div className="mt-2 pt-2 border-t border-reasoner-cyan/30">
              <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Ramp Assumption</span>
              <p className="text-xs text-reasoner-body mt-0.5">{rampAssumption}</p>
            </div>
          )}
        </div>
      )}

      {/* Interactive Replacement Scenario — Day 5 */}
      {hasReplacementUI && active && (
        <div className="bg-reasoner-paper border border-reasoner-accent rounded-lg p-5 mb-4" style={{ boxShadow: "0 4px 14px rgba(234,88,12,0.06)" }}>
          <div className="text-[10px] font-mono font-semibold text-reasoner-accent tracking-[0.12em] mb-4">
            REPLACEMENT SCENARIO · INTERACTIVE
          </div>

          <div className="flex items-center flex-wrap gap-2 text-[22px] font-medium text-reasoner-ink leading-tight">
            <span>Replace</span>
            <div className="inline-flex items-stretch border border-reasoner-line rounded-lg overflow-hidden">
              {scenarioData.availableNs.map((n) => {
                const isActive = n === activeN;
                return (
                  <button
                    key={n}
                    onClick={() => setReplaceCount(n)}
                    className={`px-3 py-1.5 font-mono tabular-nums text-[20px] font-bold transition-colors ${
                      isActive
                        ? "bg-reasoner-accent text-reasoner-paper"
                        : "bg-reasoner-paper text-reasoner-ink hover:bg-reasoner-accent-soft"
                    }`}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
            <span>SKUs</span>
            <span className="text-reasoner-accent font-mono">→</span>
            <Cite
              index={3}
              source={{
                source: "computeScenarios()",
                description:
                  "Net improvement = new product Year-1 revenue − projected annual decline of replaced SKUs. Replaced decline is computed from each SKU's revenue × |YoY growth|. New revenue scales from the baseline with diminishing-returns factors.",
                value: fmtDelta(active.net),
                formula: `newRev(${activeN}) − replaced(${activeN}) = ${fmtK(active.newRev)} − ${fmtK(active.replaced)}`,
              }}
            >
              <span
                className={`text-[28px] font-bold tabular-nums font-sans ${
                  active.net >= 0 ? "text-reasoner-green" : "text-reasoner-red"
                }`}
              >
                {fmtDelta(active.net)}
              </span>
            </Cite>
            <span className="text-reasoner-mute text-[16px]">net improvement</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-5 pt-4 border-t border-reasoner-line">
            <div>
              <div className="text-[10px] font-mono tracking-[0.1em] text-reasoner-mute">
                REPLACED DECLINE
              </div>
              <div className="text-[20px] font-mono tabular-nums font-semibold text-reasoner-red mt-1">
                −{fmtK(active.replaced)}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono tracking-[0.1em] text-reasoner-mute">
                NEW Y1 REVENUE
              </div>
              <div className="text-[20px] font-mono tabular-nums font-semibold text-reasoner-green mt-1">
                +{fmtK(active.newRev)}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono tracking-[0.1em] text-reasoner-mute">
                VENDORS AFFECTED
              </div>
              <div className="text-[13px] text-reasoner-ink mt-1.5 leading-snug">
                {active.vendorNote || "—"}
              </div>
            </div>
          </div>

          <p className="mt-4 text-[11px] font-mono text-reasoner-mute italic">
            Values recalculate in place from cached DuckDB results · no new agent run
          </p>
        </div>
      )}

      {vendorImpacts.length > 0 && (
        <div className="border-t border-reasoner-line pt-3 mb-4">
          <h4 className="text-[10px] font-mono font-semibold text-reasoner-body mb-1 tracking-[0.1em]">VENDOR IMPACT</h4>
          {vendorImpacts.map((vi, i) => (
            <div key={i} className="text-xs text-reasoner-body flex items-center gap-1.5">
              <span className={`text-[10px] font-mono font-semibold px-1 py-0.5 rounded tracking-[0.05em] ${tierBadgeColor(vi.tier)}`}>
                {vi.tier}
              </span>
              <span>{vi.vendor}: {vi.detail}</span>
            </div>
          ))}
        </div>
      )}

      {vendorNote && (
        <div className="text-[10px] text-reasoner-mute border-t border-reasoner-line pt-2 italic">
          Vendor reliability: {vendorNote}
        </div>
      )}

      {step.status === "complete" && raw && submittedPrice && !/VERDICT:\s*DECLINE/i.test(recommendationOutput ?? "") && (
        <PriceExplorer
          financialOutput={raw}
          submittedPrice={submittedPrice}
          competitorPrices={competitorPrices}
          recommendationOutput={recommendationOutput}
        />
      )}
    </ArtifactCard>
  );
}
