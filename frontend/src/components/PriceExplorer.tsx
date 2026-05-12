import { useState, useMemo } from "react";

interface Props {
  financialOutput: string;
  submittedPrice: number;
  competitorPrices: number[];
  recommendationOutput?: string;
}

function extractWeeklyUnits(output: string): number {
  const m = output.match(/WEEKLY_UNITS:\s*([\d,]+)/i);
  if (m) return parseInt(m[1].replace(/,/g, ""), 10);
  const fallback = output.match(/(\d{2,4})\s*units?\s*\/?\s*week/i);
  return fallback ? parseInt(fallback[1], 10) : 0;
}

function extractStoreCount(output: string): number {
  const m = output.match(/ROLLOUT:\s*([\d,]+)\s*stores?/i);
  if (m) return parseInt(m[1].replace(/,/g, ""), 10);
  const fallback = output.match(/([\d,]+)\s*stores?\s*initially/i);
  return fallback ? parseInt(fallback[1].replace(/,/g, ""), 10) : 600;
}

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export default function PriceExplorer({ financialOutput, submittedPrice, competitorPrices, recommendationOutput }: Props) {
  const weeklyUnits = useMemo(() => extractWeeklyUnits(financialOutput), [financialOutput]);
  const storeCount = useMemo(
    () => extractStoreCount(recommendationOutput || financialOutput),
    [recommendationOutput, financialOutput],
  );
  const [price, setPrice] = useState(submittedPrice);

  if (!weeklyUnits) return null;

  const minPrice = Math.max(0.5, Math.floor(submittedPrice * 0.5 * 4) / 4);
  const maxPrice = Math.ceil(submittedPrice * 1.5 * 4) / 4;

  // Per-store weekly units x price x 52 weeks x store count
  const expected = weeklyUnits * price * 52 * storeCount;
  const best = expected * 1.2;
  const worst = expected * 0.7;

  const avgCompetitor = competitorPrices.length > 0
    ? competitorPrices.reduce((a, b) => a + b, 0) / competitorPrices.length
    : 0;
  const priceDelta = avgCompetitor > 0 ? ((price - avgCompetitor) / avgCompetitor * 100) : 0;

  // Bar widths relative to best case
  const maxRev = best;
  const barWidth = (val: number) => `${Math.min(100, (val / maxRev) * 100)}%`;

  return (
    <div className="border-t border-gray-100 pt-3 mt-3">
      <h4 className="text-xs font-semibold text-gray-700 mb-2">What-If Price Explorer</h4>

      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-gray-500 shrink-0">${minPrice.toFixed(2)}</span>
        <input
          type="range"
          min={minPrice}
          max={maxPrice}
          step={0.25}
          value={price}
          onChange={(e) => setPrice(parseFloat(e.target.value))}
          className="flex-1 h-1.5 accent-orange-brand"
        />
        <span className="text-xs text-gray-500 shrink-0">${maxPrice.toFixed(2)}</span>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-xs text-gray-500">Price: </span>
          <span className="text-sm font-bold text-gray-900">${price.toFixed(2)}</span>
          {price !== submittedPrice && (
            <span className="text-[10px] text-gray-400 ml-1">(submitted: ${submittedPrice.toFixed(2)})</span>
          )}
        </div>
        {avgCompetitor > 0 && (
          <span className={`text-[10px] font-medium ${priceDelta > 5 ? "text-red-600" : priceDelta < -5 ? "text-green-600" : "text-gray-500"}`}>
            {priceDelta > 0 ? "+" : ""}{priceDelta.toFixed(0)}% vs avg competitor
          </span>
        )}
      </div>

      <div className="space-y-2">
        <div>
          <div className="flex items-center justify-between text-[10px] mb-0.5">
            <span className="text-gray-500">Best case</span>
            <span className="font-semibold text-gray-900">{formatCurrency(best)}/yr</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div className="bg-green-500 h-1.5 rounded-full transition-all" style={{ width: barWidth(best) }} />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between text-[10px] mb-0.5">
            <span className="text-gray-500">Expected</span>
            <span className="font-semibold text-gray-900">{formatCurrency(expected)}/yr</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: barWidth(expected) }} />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between text-[10px] mb-0.5">
            <span className="text-gray-500">Worst case</span>
            <span className="font-semibold text-gray-900">{formatCurrency(worst)}/yr</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div className="bg-red-400 h-1.5 rounded-full transition-all" style={{ width: barWidth(worst) }} />
          </div>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 mt-2">
        Based on {weeklyUnits.toLocaleString()} units/wk/store x ${price.toFixed(2)} x 52 weeks x {storeCount.toLocaleString()} stores
      </p>
    </div>
  );
}
