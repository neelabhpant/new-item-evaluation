import type { StepState, EnrichedProduct } from "../types";
import { useMemo, useState, type ReactNode } from "react";
import ArtifactCard from "./reasoner/ArtifactCard";
import { elapsedLabel } from "../hooks/useEvaluationSocket";

interface SimilarProduct {
  sku: string;
  name: string;
  brand: string;
  category: string;
  similarity_score: number;
  image_path: string;
}

interface CategoryGroup {
  category: string;
  count: number;
  max_similarity: number;
  products: SimilarProduct[];
}

interface ParsedOutput {
  basic: SimilarProduct[];
  enriched: EnrichedProduct[];
  categoryGroups: CategoryGroup[];
  inferredCategory: string;
  classification: string;
}

function parseProducts(output: string | null): ParsedOutput {
  const empty: ParsedOutput = {
    basic: [],
    enriched: [],
    categoryGroups: [],
    inferredCategory: "",
    classification: "",
  };
  if (!output) return empty;
  try {
    const parsed = JSON.parse(output);
    if (Array.isArray(parsed)) return { ...empty, basic: parsed };
    return {
      basic: parsed.similar_products ?? [],
      enriched: parsed.enriched_products ?? [],
      categoryGroups: parsed.category_groups ?? [],
      inferredCategory: parsed.inferred_category ?? "",
      classification: parsed.classification ?? "",
    };
  } catch {
    const jsonMatch = output.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
      try {
        return { ...empty, basic: JSON.parse(jsonMatch[0]) };
      } catch {
        /* ignore */
      }
    }
  }
  return empty;
}

function scoreBadgeColor(score: number): string {
  if (score >= 0.88) return "bg-red-50 text-reasoner-red";
  if (score >= 0.82) return "bg-amber-50 text-amber-700";
  return "bg-emerald-50 text-reasoner-green";
}

function scoreBorderColor(score: number): string {
  if (score >= 0.88) return "border-red-200";
  if (score >= 0.82) return "border-amber-200";
  return "border-emerald-200";
}

function classificationBadgeColor(c: string): string {
  if (c === "High Overlap") return "bg-red-50 text-reasoner-red border-red-200";
  if (c === "Moderate Overlap") return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-emerald-50 text-reasoner-green border-emerald-200";
}

function imageUrl(product: { image_path?: string; sku?: string }): string {
  if (product.image_path) {
    const filename = product.image_path.split("/").pop() ?? "";
    return `/api/images/${filename}`;
  }
  if (product.sku) return `/api/images/${product.sku}.jpg`;
  return "";
}

function formatRevenue(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function trendArrow(trend: string): { icon: string; color: string } {
  if (trend === "growing") return { icon: "↑", color: "text-reasoner-green" };
  if (trend === "declining") return { icon: "↓", color: "text-reasoner-red" };
  return { icon: "→", color: "text-reasoner-mute" };
}

interface Props {
  step: StepState | undefined;
  onProductClick?: (product: EnrichedProduct) => void;
}

function ProductRow({
  product,
  ep,
  isHighest,
  onClick,
}: {
  product: SimilarProduct;
  ep: EnrichedProduct | undefined;
  isHighest: boolean;
  onClick?: () => void;
}) {
  const score =
    product.similarity_score > 1 ? product.similarity_score / 100 : product.similarity_score;
  const trend = ep ? trendArrow(ep.trend) : null;
  const isUnderperformer = ep && (ep.trend === "declining" || ep.status === "clearance");

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${scoreBorderColor(
        score,
      )} bg-reasoner-paper ${onClick ? "cursor-pointer hover:shadow-sm transition-shadow" : ""}`}
      onClick={onClick}
    >
      <div className="w-10 h-10 rounded border border-reasoner-line overflow-hidden shrink-0 bg-reasoner-paper flex items-center justify-center">
        <img
          src={imageUrl(product)}
          alt={product.name}
          className="w-full h-full object-contain"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-reasoner-ink truncate">{product.name}</span>
          {isHighest && (
            <span className="text-[8px] font-mono font-bold bg-reasoner-line text-reasoner-mute px-1 py-0.5 rounded shrink-0 tracking-wider">
              TOP
            </span>
          )}
          {isUnderperformer && (
            <span className="text-[8px] font-mono font-bold bg-red-50 text-reasoner-red px-1 py-0.5 rounded shrink-0 tracking-wider">
              DECLINING
            </span>
          )}
          {ep && ep.status !== "active" && (
            <span
              className={`text-[8px] font-mono px-1 py-0.5 rounded shrink-0 tracking-wider ${
                ep.status === "clearance"
                  ? "bg-red-50 text-reasoner-red"
                  : "bg-reasoner-accent-soft text-reasoner-accent"
              }`}
            >
              {ep.status}
            </span>
          )}
        </div>
        <span className="text-[10px] text-reasoner-mute">{product.brand}</span>
      </div>

      {ep && ep.annual_revenue > 0 ? (
        <div className="text-right shrink-0 w-20">
          <div className="text-[10px] font-mono tabular-nums text-reasoner-body">
            {formatRevenue(ep.annual_revenue)}/yr
          </div>
          {trend && (
            <div className={`text-[10px] font-mono tabular-nums font-bold ${trend.color}`}>
              {trend.icon} {ep.yoy_growth > 0 ? "+" : ""}
              {ep.yoy_growth.toFixed(1)}%
            </div>
          )}
        </div>
      ) : (
        <div className="w-20 shrink-0" />
      )}

      {ep && (
        <div className="text-[10px] font-mono tabular-nums text-reasoner-mute w-14 text-right shrink-0">
          #{ep.velocity_rank} vel.
        </div>
      )}

      <span
        className={`text-[10px] font-mono tabular-nums font-semibold px-2 py-0.5 rounded shrink-0 ${scoreBadgeColor(
          score,
        )}`}
      >
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}

export default function SimilarityGallery({ step, onProductClick }: Props) {
  const { basic, enriched, categoryGroups, inferredCategory, classification } = useMemo(
    () => parseProducts(step?.output ?? null),
    [step?.output],
  );

  const enrichedMap = useMemo(() => {
    const m = new Map<string, EnrichedProduct>();
    for (const p of enriched) m.set(p.sku, p);
    return m;
  }, [enriched]);

  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  if (!step || step.status === "pending") return null;

  const headerAccessory: ReactNode =
    inferredCategory || classification ? (
      <div className="flex items-center gap-1.5">
        {inferredCategory && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-reasoner-accent-soft text-reasoner-accent tracking-[0.05em]">
            Detected: {inferredCategory}
          </span>
        )}
        {classification && (
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded border tracking-[0.05em] ${classificationBadgeColor(
              classification,
            )}`}
          >
            {classification}
          </span>
        )}
      </div>
    ) : null;

  if (step.status === "running") {
    return (
      <ArtifactCard
        agent="▸ VISUAL SIMILARITY"
        status="running"
        tone="running"
        title="Searching across all categories…"
      >
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="relative overflow-hidden rounded-lg h-12 bg-reasoner-line/40"
            >
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, rgba(234,88,12,0.10), transparent)",
                  backgroundSize: "200% 100%",
                  animation: "shimmer 2.2s infinite",
                }}
              />
            </div>
          ))}
        </div>
      </ArtifactCard>
    );
  }

  const allProducts =
    categoryGroups.length > 0 ? categoryGroups.flatMap((g) => g.products) : basic;
  const maxScore =
    allProducts.length > 0
      ? Math.max(
          ...allProducts.map((p) =>
            p.similarity_score > 1 ? p.similarity_score / 100 : p.similarity_score,
          ),
        )
      : 0;
  const hasGroups = categoryGroups.length > 0;

  const toggleGroup = (cat: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const renderProducts = (products: SimilarProduct[]) =>
    products.map((product) => (
      <ProductRow
        key={product.sku}
        product={product}
        ep={enrichedMap.get(product.sku)}
        isHighest={
          (product.similarity_score > 1
            ? product.similarity_score / 100
            : product.similarity_score) === maxScore
        }
        onClick={
          onProductClick && enrichedMap.get(product.sku)
            ? () => onProductClick(enrichedMap.get(product.sku)!)
            : undefined
        }
      />
    ));

  const title = hasGroups
    ? `Found ${allProducts.length} matches across ${categoryGroups.length} categories`
    : "Analysis of existing products in the market";

  const summary = hasGroups
    ? `Found ${allProducts.length} matches across ${categoryGroups.length} categories · max ${(maxScore * 100).toFixed(0)}%`
    : `${basic.length} comparable products found`;

  return (
    <ArtifactCard
      agent="▸ VISUAL SIMILARITY"
      status={step.status === "error" ? "error" : "done"}
      elapsed={elapsedLabel(step)}
      title={title}
      headerAccessory={headerAccessory}
      summary={summary}
      anchorId="similarity-artifact"
    >
      {hasGroups ? (
        <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
          {categoryGroups.map((group) => {
            const isPrimary = group.category === inferredCategory;
            const isExpanded = isPrimary || expandedGroups.has(group.category);
            const displayProducts = isPrimary
              ? group.products.slice(0, 5)
              : isExpanded
                ? group.products.slice(0, 4)
                : [];

            return (
              <div key={group.category}>
                <div
                  className={`flex items-center justify-between py-1 ${
                    !isPrimary ? "cursor-pointer" : ""
                  }`}
                  onClick={!isPrimary ? () => toggleGroup(group.category) : undefined}
                >
                  <div className="flex items-center gap-2">
                    {!isPrimary && (
                      <svg
                        className={`w-3 h-3 text-reasoner-dim transition-transform ${
                          isExpanded ? "rotate-90" : ""
                        }`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    )}
                    <span
                      className={`text-xs font-semibold ${
                        isPrimary ? "text-reasoner-ink" : "text-reasoner-body"
                      }`}
                    >
                      {isPrimary ? "Primary" : "Adjacent"}: {group.category}
                    </span>
                    <span className="text-[10px] font-mono tabular-nums text-reasoner-dim">
                      {group.count} product{group.count !== 1 ? "s" : ""} · max{" "}
                      {(group.max_similarity * 100).toFixed(0)}%
                    </span>
                  </div>
                  {!isPrimary && !isExpanded && (
                    <span
                      className={`text-[9px] font-mono tabular-nums font-semibold px-1.5 py-0.5 rounded ${scoreBadgeColor(
                        group.max_similarity,
                      )}`}
                    >
                      {(group.max_similarity * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {displayProducts.length > 0 && (
                  <div className="space-y-1 mt-1">{renderProducts(displayProducts)}</div>
                )}
              </div>
            );
          })}
        </div>
      ) : basic.length > 0 ? (
        <div className="space-y-1 max-h-[480px] overflow-y-auto pr-1">
          {renderProducts(basic.slice(0, 10))}
        </div>
      ) : (
        <div className="text-sm text-reasoner-mute">
          {step.output ? (
            <div className="whitespace-pre-wrap text-xs bg-reasoner-bg rounded p-3 max-h-60 overflow-y-auto font-mono">
              {step.output.slice(0, 2000)}
            </div>
          ) : (
            "No similar products found."
          )}
        </div>
      )}
    </ArtifactCard>
  );
}
