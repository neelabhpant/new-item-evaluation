import { useCallback, useEffect, useMemo, useState } from "react";
import type { EnrichedProduct } from "./types";
import ReasonerHeader from "./components/reasoner/ReasonerHeader";
import EvaluateShell from "./components/reasoner/EvaluateShell";
import ReasoningStream from "./components/reasoner/ReasoningStream";
import WorkflowStepper from "./components/WorkflowStepper";
import SubmissionPanel from "./components/SubmissionPanel";
import SimilarityGallery from "./components/SimilarityGallery";
import RiskAssessment from "./components/RiskAssessment";
import MarketContext from "./components/MarketContext";
import FinancialSummary from "./components/FinancialSummary";
import VerdictHero from "./components/reasoner/VerdictHero";
import FollowupPrompt from "./components/reasoner/FollowupPrompt";
import LastSessionReplay, { type HistoryRow, type RestoreResult } from "./components/reasoner/LastSessionReplay";
import type { SubmissionInitial } from "./components/SubmissionPanel";
import ProductComparison from "./components/ProductComparison";
import PlanogramView from "./components/PlanogramView";
import CatalogDashboard from "./components/CatalogDashboard";
import EvaluationHistory from "./components/EvaluationHistory";
import MerchantQueue from "./components/MerchantQueue";
import SupplierPortal from "./components/SupplierPortal";
import BatchEvaluation from "./components/BatchEvaluation";
import { useEvaluationSocket, elapsedLabel } from "./hooks/useEvaluationSocket";
import type { AgentState, AgentSpec } from "./components/reasoner/AgentRail";
import type { StepState } from "./types";

interface SubmittedData {
  name: string;
  price: number;
  category: string;
  claims: string;
  image: string | null;
}

function App() {
  const [activeTab, setActiveTab] = useState<"evaluate" | "catalog" | "history" | "merchant" | "supplier" | "batch">("evaluate");
  const { steps, isRunning, isDone, finalOutput, evaluationId, connect, restoreFromResult } = useEvaluationSocket();
  const [submittedData, setSubmittedData] = useState<SubmittedData | null>(null);
  const [comparisonProduct, setComparisonProduct] = useState<EnrichedProduct | null>(null);
  const [submissionInitial, setSubmissionInitial] = useState<(SubmissionInitial & { _version: number }) | undefined>(undefined);
  const [replayRefreshKey, setReplayRefreshKey] = useState(0);

  const handleSubmit = useCallback(
    async (data: {
      name: string;
      description: string;
      price: number;
      category: string;
      claims: string;
      image: string | null;
    }) => {
      setSubmittedData({ name: data.name, price: data.price, category: data.category, claims: data.claims, image: data.image });
      const resp = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const { evaluation_id } = await resp.json();
      connect(evaluation_id);
    },
    [connect]
  );

  const similarityStep = steps[1];
  const riskMarketStep = steps[3];
  const financialStep = steps[4];
  const recommendationStep = steps[5];

  const agentStateFromStep = (s: StepState | undefined): AgentState => {
    if (!s || s.status === "pending") return "idle";
    if (s.status === "complete") return "done";
    return "running";
  };

  const agentStates: Partial<Record<AgentSpec["id"], AgentState>> = {
    risk: agentStateFromStep(riskMarketStep),
    fin: agentStateFromStep(financialStep),
    synth: agentStateFromStep(recommendationStep),
  };
  const agentElapsed: Partial<Record<AgentSpec["id"], string>> = {
    risk: elapsedLabel(riskMarketStep),
    fin: elapsedLabel(financialStep),
    synth: elapsedLabel(recommendationStep),
  };

  const handleReplay = useCallback(
    (result: RestoreResult) => {
      const sub = (result.data_package as { submission?: Record<string, unknown> })?.submission ?? {};
      setSubmittedData({
        name: String(sub.name ?? ""),
        price: Number(sub.price ?? 0),
        category: String(sub.category ?? ""),
        claims: Array.isArray(sub.claims) ? (sub.claims as string[]).join(", ") : String(sub.claims ?? ""),
        image: null,
      });
      restoreFromResult(result);
    },
    [restoreFromResult],
  );

  const handleBranch = useCallback((row: HistoryRow) => {
    setSubmissionInitial({
      name: row.product_name,
      description: "",
      price: row.price,
      category: row.category || "Auto-detect",
      claims: row.claims ? row.claims.split(",").map((c) => c.trim()).filter(Boolean) : [],
      _version: Date.now(),
    });
  }, []);

  // Bump the replay panel's refresh key when an evaluation finishes so it
  // re-fetches and picks up the latest cached result.
  useEffect(() => {
    if (isDone) setReplayRefreshKey((k) => k + 1);
  }, [isDone]);

  const handleJumpTo = useCallback((agentId: AgentSpec["id"]) => {
    const map: Record<AgentSpec["id"], string> = {
      risk: "risk-artifact",
      fin: "fin-artifact",
      synth: "verdict-artifact",
    };
    const el = document.getElementById(map[agentId]);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    el.setAttribute("data-pulsing", "true");
    window.setTimeout(() => el.removeAttribute("data-pulsing"), 1600);
  }, []);

  const hasResults =
    similarityStep?.status === "complete" ||
    similarityStep?.status === "running";

  const hasAnalysis =
    riskMarketStep?.status === "running" ||
    riskMarketStep?.status === "complete" ||
    financialStep?.status === "running" ||
    financialStep?.status === "complete";

  const enrichedProducts = useMemo<EnrichedProduct[]>(() => {
    if (!similarityStep?.output) return [];
    try {
      const parsed = JSON.parse(similarityStep.output);
      return parsed.enriched_products ?? [];
    } catch {
      return [];
    }
  }, [similarityStep?.output]);

  return (
    <div className="min-h-screen bg-reasoner-bg flex flex-col">
      <ReasonerHeader activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === "catalog" ? (
        <CatalogDashboard />
      ) : activeTab === "history" ? (
        <EvaluationHistory />
      ) : activeTab === "merchant" ? (
        <MerchantQueue />
      ) : activeTab === "supplier" ? (
        <SupplierPortal />
      ) : activeTab === "batch" ? (
        <BatchEvaluation />
      ) : (
        <EvaluateShell agentStates={agentStates} agentElapsed={agentElapsed} onJumpTo={handleJumpTo}>
          {!hasResults && !isRunning && (
            <div className="max-w-3xl mb-8">
              <div className="text-[11px] font-mono text-reasoner-mute tracking-[0.18em] mb-3">
                NEW EVALUATION · ⌘N
              </div>
              <h1 className="text-[44px] font-bold text-reasoner-ink tracking-tight leading-[1.05]">
                Ask three agents anything about a new product.
              </h1>
              <p className="text-[16px] text-reasoner-mute mt-4 max-w-2xl leading-relaxed">
                Drop a product in. Image, price, claims. Risk, Financial, and Merchandising reason through it in about fifteen seconds.
              </p>
            </div>
          )}

          <WorkflowStepper steps={steps} />
          <div className="flex gap-6 mt-4">
            <div className="w-72 shrink-0">
              <SubmissionPanel onSubmit={handleSubmit} isRunning={isRunning} initialValues={submissionInitial} />
            </div>

            <div className="flex-1 space-y-4 min-w-0">
              {hasResults && (
                <SimilarityGallery step={similarityStep} onProductClick={setComparisonProduct} />
              )}

              {hasAnalysis && (
                <div className="space-y-4">
                  {riskMarketStep?.reasoning && (
                    <ReasoningStream
                      text={riskMarketStep.reasoning}
                      agent="▸ RISK & MARKET ANALYST"
                    />
                  )}
                  <RiskAssessment step={riskMarketStep} />
                  <MarketContext step={riskMarketStep} />

                  {financialStep?.reasoning && (
                    <ReasoningStream
                      text={financialStep.reasoning}
                      agent="▸ FINANCIAL PROJECTOR"
                    />
                  )}
                  <FinancialSummary
                    step={financialStep}
                    submittedPrice={submittedData?.price}
                    recommendationOutput={recommendationStep?.output ?? undefined}
                    enrichedProducts={enrichedProducts}
                  />

                  {recommendationStep?.reasoning && (
                    <ReasoningStream
                      text={recommendationStep.reasoning}
                      agent="▸ MERCHANDISING LEAD"
                    />
                  )}
                  <VerdictHero
                    step={recommendationStep}
                    finalOutput={finalOutput}
                    isDone={isDone}
                    productName={submittedData?.name}
                  />

                  {isDone && evaluationId && (
                    <FollowupPrompt evaluationId={evaluationId} productName={submittedData?.name} />
                  )}
                </div>
              )}

              {!hasAnalysis && isRunning && hasResults && (
                <VerdictHero
                  step={recommendationStep}
                  finalOutput={finalOutput}
                  isDone={isDone}
                />
              )}

              {enrichedProducts.length > 0 && similarityStep?.status === "complete" && (
                <PlanogramView
                  products={enrichedProducts}
                  submittedName={submittedData?.name}
                />
              )}
            </div>
          </div>

          {!isRunning && !isDone && (
            <LastSessionReplay
              refreshKey={replayRefreshKey}
              onReplay={handleReplay}
              onBranch={handleBranch}
            />
          )}
        </EvaluateShell>
      )}
      {comparisonProduct && submittedData && (
        <ProductComparison
          submitted={submittedData}
          competitor={comparisonProduct}
          onClose={() => setComparisonProduct(null)}
        />
      )}
    </div>
  );
}

export default App;
