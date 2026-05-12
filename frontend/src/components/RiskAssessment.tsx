import type { StepState } from "../types";
import CannibalizationTable from "./CannibalizationTable";
import ArtifactCard from "./reasoner/ArtifactCard";
import Cite from "./reasoner/Cite";
import { elapsedLabel } from "../hooks/useEvaluationSocket";

interface Props {
  step: StepState | undefined;
}

function strip(text: string): string {
  return text.replace(/\*\*/g, "");
}

function extractRiskLevel(output: string): string {
  const labeled = output.match(/RISK_RATING:\s*(HIGH|MEDIUM|LOW)/i);
  if (labeled) return labeled[1].toUpperCase();
  const match = output.match(/(?:overall|risk)\s*(?:risk)?\s*(?:rating|level|score|assessment)[:\s]*(?:is\s+)?["']?(\w+)/i);
  if (match) return match[1].toUpperCase();
  if (/\bhigh\s+risk\b/i.test(output)) return "HIGH";
  if (/\bmedium\s+risk\b/i.test(output)) return "MEDIUM";
  if (/\blow\s+risk\b/i.test(output)) return "LOW";
  return "";
}

function extractNetImpact(output: string): string {
  const labeled = output.match(/NET_CATEGORY_IMPACT:\s*([^\n]+)/i);
  if (labeled) return strip(labeled[1].trim());
  const match = output.match(/net\s+(?:category\s+)?impact[:\s]*([^\n]+)/i);
  return match ? strip(match[1].trim()) : "";
}

function hasCannibalizationDetails(output: string): boolean {
  return /CANNIBALIZATION_DETAILS:/i.test(output);
}

function isWhiteSpace(output: string): boolean {
  return /OPPORTUNITY_TYPE:/i.test(output);
}

function extractOpportunityType(output: string): string {
  const m = output.match(/OPPORTUNITY_TYPE:\s*([^\n]+)/i);
  return m ? strip(m[1].trim()) : "";
}

function extractMarketOpportunity(output: string): string {
  const m = output.match(/MARKET_OPPORTUNITY:\s*([^\n]+)/i);
  return m ? strip(m[1].trim()) : "";
}

function extractNearestCategories(output: string): string {
  const m = output.match(/NEAREST_CATEGORIES:\s*([^\n]+)/i);
  return m ? strip(m[1].trim()) : "";
}

function extractDemandSignals(output: string): string {
  const m = output.match(/DEMAND_SIGNALS:\s*([^\n]+)/i);
  return m ? strip(m[1].trim()) : "";
}

function riskBadgeColor(level: string): string {
  if (level === "HIGH") return "bg-reasoner-red text-reasoner-paper";
  if (level === "MEDIUM") return "bg-amber-600 text-white";
  return "bg-reasoner-green text-reasoner-paper";
}

export default function RiskAssessment({ step }: Props) {
  if (!step || step.status === "pending") return null;

  const status = step.status === "error" ? "error" : step.status === "running" ? "running" : "done";
  const tone = step.status === "running" ? "running" : "default";

  if (step.status === "running") {
    return (
      <ArtifactCard
        agent="▸ RISK & MARKET ANALYST"
        status={status}
        tone={tone}
        title="Cannibalization Risk Assessment"
      >
        <div className="animate-pulse space-y-2">
          <div className="h-5 bg-reasoner-line/50 rounded w-24" />
          <div className="h-4 bg-reasoner-line/50 rounded w-full" />
          <div className="h-4 bg-reasoner-line/50 rounded w-3/4" />
          <div className="h-4 bg-reasoner-line/50 rounded w-5/6" />
        </div>
      </ArtifactCard>
    );
  }

  const raw = step.output ? strip(step.output) : "";
  const riskLevel = raw ? extractRiskLevel(raw) : "";
  const netImpact = raw ? extractNetImpact(raw) : "";
  const whiteSpace = raw ? isWhiteSpace(raw) : false;

  const riskBadge = riskLevel ? (
    <Cite
      index={1}
      source={{
        source: "risk_agent.assess_overlap()",
        description:
          "HIGH risk when similarity overlap exceeds 88% AND the category is saturated (≥15 SKUs). MEDIUM for moderate overlap (82–88%). LOW for white space (<82%).",
        value: `${riskLevel} RISK`,
        formula: "max(similarity_score) × category_saturation",
      }}
    >
      <span className={`inline-block text-[10px] font-mono font-bold px-2.5 py-0.5 rounded tracking-[0.08em] ${riskBadgeColor(riskLevel)}`}>
        {riskLevel} RISK
      </span>
    </Cite>
  ) : null;

  if (whiteSpace) {
    const opportunityType = extractOpportunityType(raw);
    const marketOpportunity = extractMarketOpportunity(raw);
    const nearestCategories = extractNearestCategories(raw);
    const demandSignals = extractDemandSignals(raw);

    const headerAccessory = (
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded bg-reasoner-cyan text-reasoner-paper tracking-[0.08em]">
          NEW CATEGORY
        </span>
        {riskBadge}
      </div>
    );

    const wsSummary = [opportunityType && `NEW CATEGORY · ${opportunityType}`, netImpact]
      .filter(Boolean)
      .join(" · ") || "NEW CATEGORY opportunity";

    return (
      <ArtifactCard
        agent="▸ RISK & MARKET ANALYST"
        status={status}
        elapsed={elapsedLabel(step)}
        title="Market Opportunity Assessment"
        headerAccessory={headerAccessory}
        summary={wsSummary}
        anchorId="risk-artifact"
      >
        <div className="space-y-3">
          {opportunityType && (
            <div>
              <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Opportunity Type</span>
              <p className="text-sm font-semibold text-reasoner-ink mt-0.5">{opportunityType}</p>
            </div>
          )}

          {marketOpportunity && (
            <div>
              <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Market Opportunity</span>
              <p className="text-xs text-reasoner-body leading-relaxed mt-0.5">{marketOpportunity}</p>
            </div>
          )}

          {nearestCategories && (
            <div>
              <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Nearest Categories</span>
              <p className="text-xs text-reasoner-body leading-relaxed mt-0.5">{nearestCategories}</p>
            </div>
          )}

          {demandSignals && (
            <div>
              <span className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">Demand Signals</span>
              <p className="text-xs text-reasoner-body leading-relaxed mt-0.5">{demandSignals}</p>
            </div>
          )}
        </div>

        {netImpact && (
          <div className="mt-3 pt-3 border-t border-reasoner-line text-xs text-reasoner-mute">
            <span className="font-medium text-reasoner-ink">Net category impact:</span>{" "}
            <Cite
              index={2}
              source={{
                source: "risk_agent.estimate_category_impact()",
                description:
                  "Net dollar impact to the category, summing per-SKU cannibalization estimates against any replacement offset the agent identified.",
                value: netImpact,
              }}
            >
              <span className="font-mono tabular-nums">{netImpact}</span>
            </Cite>
          </div>
        )}
      </ArtifactCard>
    );
  }

  const hasDetailedTable = step.output ? hasCannibalizationDetails(step.output) : false;

  const overlapSummary = [riskLevel && `${riskLevel} RISK`, netImpact]
    .filter(Boolean)
    .join(" · ") || "Cannibalization assessed";

  return (
    <ArtifactCard
      agent="▸ RISK & MARKET ANALYST"
      status={status}
      elapsed={elapsedLabel(step)}
      title="Cannibalization Risk Assessment"
      headerAccessory={riskBadge}
      summary={overlapSummary}
      anchorId="risk-artifact"
    >
      {hasDetailedTable && step.output ? (
        <CannibalizationTable output={step.output} />
      ) : raw ? (
        <div className="text-xs text-reasoner-body whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
          {raw.slice(0, 1500)}
        </div>
      ) : null}

      {netImpact && (
        <div className="mt-3 pt-3 border-t border-reasoner-line text-xs text-reasoner-mute">
          <span className="font-medium text-reasoner-ink">Net category impact:</span>{" "}
          <span className="font-mono tabular-nums">{netImpact}</span>
        </div>
      )}
    </ArtifactCard>
  );
}
