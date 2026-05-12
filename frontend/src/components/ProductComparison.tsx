import type { EnrichedProduct } from "../types";

interface SubmittedProduct {
  name: string;
  price: number;
  category: string;
  claims: string;
  image: string | null;
}

interface Props {
  submitted: SubmittedProduct;
  competitor: EnrichedProduct;
  onClose: () => void;
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

function parseClaims(claims: string): string[] {
  if (!claims) return [];
  return claims.split(",").map((c) => c.trim()).filter(Boolean);
}

function priceDelta(submitted: number, competitor: number): { text: string; color: string } {
  if (!competitor || competitor === 0) return { text: "", color: "" };
  const diff = ((submitted - competitor) / competitor) * 100;
  if (Math.abs(diff) < 1) return { text: "Same price", color: "text-gray-500" };
  if (diff > 0) return { text: `${diff.toFixed(0)}% higher`, color: "text-red-600" };
  return { text: `${Math.abs(diff).toFixed(0)}% lower`, color: "text-green-600" };
}

function tierColor(tier: string): string {
  if (tier === "Strategic") return "bg-blue-100 text-blue-700";
  if (tier === "Preferred") return "bg-green-100 text-green-700";
  if (tier === "Probationary") return "bg-red-100 text-red-700";
  return "bg-gray-100 text-gray-600";
}

export default function ProductComparison({ submitted, competitor, onClose }: Props) {
  const submittedClaims = parseClaims(submitted.claims);
  const competitorClaims = parseClaims(competitor.claims || "");
  const sharedClaims = submittedClaims.filter((c) =>
    competitorClaims.some((cc) => cc.toLowerCase() === c.toLowerCase()),
  );
  const uniqueSubmitted = submittedClaims.filter(
    (c) => !competitorClaims.some((cc) => cc.toLowerCase() === c.toLowerCase()),
  );
  const uniqueCompetitor = competitorClaims.filter(
    (c) => !submittedClaims.some((sc) => sc.toLowerCase() === c.toLowerCase()),
  );
  const delta = priceDelta(submitted.price, competitor.price);
  const simPct = (competitor.similarity_score * 100).toFixed(0);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">Product Comparison</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        <div className="p-6">
          {/* Two-column product headers */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            {/* Submitted product */}
            <div className="text-center">
              <div className="text-[10px] font-semibold text-blue-600 uppercase tracking-wide mb-2">Your Product</div>
              <div className="w-32 h-32 mx-auto bg-gray-50 rounded-lg overflow-hidden flex items-center justify-center mb-2 border border-gray-200">
                {submitted.image ? (
                  <img src={`data:image/jpeg;base64,${submitted.image}`} alt={submitted.name} className="w-full h-full object-contain" />
                ) : (
                  <span className="text-gray-300 text-3xl">?</span>
                )}
              </div>
              <p className="text-sm font-semibold text-gray-900">{submitted.name}</p>
              <p className="text-xs text-gray-500">{submitted.category}</p>
            </div>

            {/* Competitor product */}
            <div className="text-center">
              <div className="text-[10px] font-semibold text-orange-600 uppercase tracking-wide mb-2">Competitor</div>
              <div className="w-32 h-32 mx-auto bg-gray-50 rounded-lg overflow-hidden flex items-center justify-center mb-2 border border-gray-200">
                <img
                  src={imageUrl(competitor)}
                  alt={competitor.name}
                  className="w-full h-full object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
              <p className="text-sm font-semibold text-gray-900">{competitor.name}</p>
              <p className="text-xs text-gray-500">{competitor.brand} | {competitor.category}</p>
            </div>
          </div>

          {/* Similarity score bar */}
          <div className="bg-gray-50 rounded-lg p-3 mb-4">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-gray-500">Visual + Text Similarity</span>
              <span className="font-semibold text-gray-900">{simPct}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${
                  competitor.similarity_score >= 0.92 ? "bg-red-500" :
                  competitor.similarity_score >= 0.88 ? "bg-amber-500" : "bg-green-500"
                }`}
                style={{ width: `${simPct}%` }}
              />
            </div>
          </div>

          {/* Price comparison */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <span className="text-[10px] text-gray-500 uppercase tracking-wide">Your Price</span>
              <p className="text-lg font-bold text-gray-900">${submitted.price.toFixed(2)}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <span className="text-[10px] text-gray-500 uppercase tracking-wide">Competitor Price</span>
              <p className="text-lg font-bold text-gray-900">${competitor.price.toFixed(2)}</p>
              {delta.text && (
                <span className={`text-xs font-medium ${delta.color}`}>{delta.text}</span>
              )}
            </div>
          </div>

          {/* Claims comparison */}
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-gray-700 mb-2">Claims Comparison</h3>
            <div className="flex flex-wrap gap-1.5">
              {sharedClaims.map((c) => (
                <span key={c} className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700 border border-green-200">
                  {c}
                </span>
              ))}
              {uniqueSubmitted.map((c) => (
                <span key={`s-${c}`} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200">
                  {c} (yours only)
                </span>
              ))}
              {uniqueCompetitor.map((c) => (
                <span key={`c-${c}`} className="text-[10px] px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 border border-orange-200">
                  {c} (competitor only)
                </span>
              ))}
              {sharedClaims.length === 0 && uniqueSubmitted.length === 0 && uniqueCompetitor.length === 0 && (
                <span className="text-xs text-gray-400">No claims data available</span>
              )}
            </div>
          </div>

          {/* Competitor financials */}
          {competitor.annual_revenue > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-semibold text-gray-700 mb-2">Competitor Performance</h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-[10px] text-gray-500 block">Annual Revenue</span>
                  <span className="text-sm font-semibold text-gray-900">{formatRevenue(competitor.annual_revenue)}</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-[10px] text-gray-500 block">Weekly Units</span>
                  <span className="text-sm font-semibold text-gray-900">{competitor.weekly_units.toLocaleString()}</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-[10px] text-gray-500 block">YoY Growth</span>
                  <span className={`text-sm font-semibold ${competitor.yoy_growth > 0 ? "text-green-600" : competitor.yoy_growth < 0 ? "text-red-600" : "text-gray-600"}`}>
                    {competitor.yoy_growth > 0 ? "+" : ""}{competitor.yoy_growth.toFixed(1)}%
                  </span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-[10px] text-gray-500 block">Margin</span>
                  <span className="text-sm font-semibold text-gray-900">{competitor.margin_pct.toFixed(1)}%</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-[10px] text-gray-500 block">Velocity Rank</span>
                  <span className="text-sm font-semibold text-gray-900">#{competitor.velocity_rank}</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-[10px] text-gray-500 block">Status</span>
                  <span className={`text-sm font-semibold ${competitor.status === "clearance" ? "text-red-600" : "text-gray-900"}`}>
                    {competitor.status}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Vendor info */}
          {competitor.vendor_relationship_tier && competitor.vendor_relationship_tier !== "Unknown" && (
            <div>
              <h3 className="text-xs font-semibold text-gray-700 mb-2">Vendor: {competitor.brand}</h3>
              <div className="flex items-center gap-3 text-xs">
                <span className={`font-semibold px-2 py-0.5 rounded ${tierColor(competitor.vendor_relationship_tier)}`}>
                  {competitor.vendor_relationship_tier}
                </span>
                <span className="text-gray-500">Fill: {competitor.vendor_fill_rate.toFixed(0)}%</span>
                <span className="text-gray-500">OTIF: {competitor.vendor_otif_score.toFixed(0)}%</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
