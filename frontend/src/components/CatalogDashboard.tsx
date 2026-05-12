import { useEffect, useState } from "react";

interface CategoryCount {
  category: string;
  count: number;
}

interface BrandCount {
  brand: string;
  count: number;
}

interface Benchmark {
  category: string;
  market_size: number;
  yoy_growth: number;
  avg_margin: number;
  avg_price: number;
  sku_count: number;
  top_trend: string;
}

interface Summary {
  total_products: number;
  total_brands: number;
  total_categories: number;
  avg_price: number;
  categories: CategoryCount[];
  top_brands: BrandCount[];
  benchmarks: Benchmark[];
}

interface Product {
  sku: string;
  name: string;
  brand: string;
  category: string;
  price: number;
  status: string;
  annual_revenue: number;
  weekly_units: number;
  trend: string;
  yoy_growth: number;
}

function fmt(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function trendColor(trend: string): string {
  if (trend === "growing") return "text-reasoner-green";
  if (trend === "declining") return "text-reasoner-red";
  return "text-reasoner-mute";
}

function statusBadge(status: string): string {
  if (status === "active") return "bg-reasoner-green/15 text-reasoner-green";
  if (status === "clearance") return "bg-red-50 text-reasoner-red";
  if (status === "seasonal") return "bg-reasoner-cyan/15 text-reasoner-cyan";
  if (status === "new") return "bg-reasoner-violet/15 text-reasoner-violet";
  return "bg-reasoner-line/50 text-reasoner-mute";
}

export default function CatalogDashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [filter, setFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sortCol, setSortCol] = useState<keyof Product>("annual_revenue");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    fetch("/api/catalog/summary").then(r => r.json()).then(setSummary);
    fetch("/api/catalog/products").then(r => r.json()).then(setProducts);
  }, []);

  if (!summary) {
    return (
      <div className="flex-1 p-6 flex items-center justify-center">
        <div className="animate-pulse text-reasoner-mute font-mono text-[12px] tracking-[0.08em]">
          LOADING CATALOG DATA…
        </div>
      </div>
    );
  }

  const maxCategoryCount = Math.max(...summary.categories.map(c => c.count));

  const filtered = products.filter(p => {
    const text = filter.toLowerCase();
    const matchesText = !text || p.name.toLowerCase().includes(text) || p.brand.toLowerCase().includes(text);
    const matchesCat = !categoryFilter || p.category === categoryFilter;
    return matchesText && matchesCat;
  });

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortCol];
    const bv = b[sortCol];
    if (typeof av === "number" && typeof bv === "number") {
      return sortDir === "asc" ? av - bv : bv - av;
    }
    return sortDir === "asc"
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av));
  });

  function handleSort(col: keyof Product) {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
  }

  const sortArrow = (col: keyof Product) =>
    sortCol === col ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div className="flex-1 p-6 bg-reasoner-bg">
      <div className="max-w-[1400px] mx-auto space-y-6">
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Total Products", value: summary.total_products.toLocaleString() },
            { label: "Brands", value: summary.total_brands.toLocaleString() },
            { label: "Categories", value: summary.total_categories.toLocaleString() },
            { label: "Avg Price", value: `$${summary.avg_price.toFixed(2)}` },
          ].map(s => (
            <div key={s.label} className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
              <p className="text-[10px] font-mono text-reasoner-mute uppercase tracking-[0.12em]">{s.label}</p>
              <p className="text-2xl font-bold font-mono tabular-nums text-reasoner-ink mt-1">{s.value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
            <h3 className="text-sm font-semibold text-reasoner-ink mb-4">Products by Category</h3>
            <div className="space-y-2">
              {summary.categories.map(c => (
                <div key={c.category} className="flex items-center gap-3">
                  <span className="text-xs text-reasoner-body w-32 shrink-0 truncate" title={c.category}>
                    {c.category}
                  </span>
                  <div className="flex-1 h-5 bg-reasoner-line/50 rounded overflow-hidden">
                    <div
                      className="h-full bg-reasoner-accent rounded transition-all"
                      style={{ width: `${(c.count / maxCategoryCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono tabular-nums font-semibold text-reasoner-ink w-8 text-right">{c.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
            <h3 className="text-sm font-semibold text-reasoner-ink mb-4">Top Brands</h3>
            <div className="space-y-2">
              {summary.top_brands.map(b => (
                <div key={b.brand} className="flex items-center gap-3">
                  <span className="text-xs text-reasoner-body w-36 shrink-0 truncate" title={b.brand}>
                    {b.brand}
                  </span>
                  <div className="flex-1 h-5 bg-reasoner-line/50 rounded overflow-hidden">
                    <div
                      className="h-full bg-reasoner-cyan rounded transition-all"
                      style={{ width: `${(b.count / summary.top_brands[0].count) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono tabular-nums font-semibold text-reasoner-ink w-8 text-right">{b.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
          <h3 className="text-sm font-semibold text-reasoner-ink mb-4">Category Benchmarks</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-reasoner-line">
                  <th className="text-left py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">Category</th>
                  <th className="text-right py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">Market Size</th>
                  <th className="text-right py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">YoY Growth</th>
                  <th className="text-right py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">Avg Margin</th>
                  <th className="text-right py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">Avg Price</th>
                  <th className="text-right py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">SKUs</th>
                  <th className="text-left py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px]">Top Trend</th>
                </tr>
              </thead>
              <tbody>
                {summary.benchmarks.map(b => (
                  <tr key={b.category} className="border-b border-reasoner-line/60 hover:bg-reasoner-bg">
                    <td className="py-2 px-2 font-medium text-reasoner-ink">{b.category}</td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-reasoner-body">{fmt(b.market_size)}</td>
                    <td className={`py-2 px-2 text-right font-mono tabular-nums font-medium ${b.yoy_growth >= 0 ? "text-reasoner-green" : "text-reasoner-red"}`}>
                      {b.yoy_growth >= 0 ? "+" : ""}{b.yoy_growth.toFixed(1)}%
                    </td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-reasoner-body">{b.avg_margin.toFixed(1)}%</td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-reasoner-body">${b.avg_price.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-reasoner-body">{b.sku_count}</td>
                    <td className="py-2 px-2 text-reasoner-mute max-w-48 truncate" title={b.top_trend}>{b.top_trend}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-reasoner-ink">
              Product Catalog <span className="font-mono tabular-nums text-reasoner-mute font-normal">({filtered.length} products)</span>
            </h3>
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="Search name or brand…"
                value={filter}
                onChange={e => setFilter(e.target.value)}
                className="border border-reasoner-line rounded px-3 py-1.5 text-xs w-56 bg-reasoner-paper text-reasoner-ink placeholder:text-reasoner-dim focus:outline-none focus:ring-2 focus:ring-reasoner-accent/40 focus:border-reasoner-accent"
              />
              <select
                value={categoryFilter}
                onChange={e => setCategoryFilter(e.target.value)}
                className="border border-reasoner-line rounded px-3 py-1.5 text-xs bg-reasoner-paper text-reasoner-ink focus:outline-none focus:ring-2 focus:ring-reasoner-accent/40 focus:border-reasoner-accent"
              >
                <option value="">All Categories</option>
                {summary.categories.map(c => (
                  <option key={c.category} value={c.category}>{c.category} ({c.count})</option>
                ))}
              </select>
            </div>
          </div>
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-reasoner-paper">
                <tr className="border-b border-reasoner-line">
                  {([
                    ["name", "Product Name"],
                    ["brand", "Brand"],
                    ["category", "Category"],
                    ["price", "Price"],
                    ["status", "Status"],
                    ["annual_revenue", "Annual Revenue"],
                    ["weekly_units", "Units/Wk"],
                    ["trend", "Trend"],
                    ["yoy_growth", "YoY"],
                  ] as [keyof Product, string][]).map(([col, label]) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className={`py-2 px-2 font-mono font-semibold text-reasoner-mute tracking-[0.05em] uppercase text-[10px] cursor-pointer hover:text-reasoner-ink select-none ${
                        col === "name" || col === "brand" || col === "category" || col === "status" || col === "trend" ? "text-left" : "text-right"
                      }`}
                    >
                      {label}{sortArrow(col)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.slice(0, 200).map(p => (
                  <tr key={p.sku} className="border-b border-reasoner-line/60 hover:bg-reasoner-bg">
                    <td className="py-1.5 px-2 text-reasoner-ink max-w-56 truncate" title={p.name}>{p.name}</td>
                    <td className="py-1.5 px-2 text-reasoner-body max-w-28 truncate" title={p.brand}>{p.brand}</td>
                    <td className="py-1.5 px-2 text-reasoner-body">{p.category}</td>
                    <td className="py-1.5 px-2 text-right font-mono tabular-nums text-reasoner-body">${p.price.toFixed(2)}</td>
                    <td className="py-1.5 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-medium tracking-[0.05em] ${statusBadge(p.status)}`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono tabular-nums font-medium text-reasoner-ink">{fmt(p.annual_revenue)}</td>
                    <td className="py-1.5 px-2 text-right font-mono tabular-nums text-reasoner-body">{p.weekly_units.toLocaleString()}</td>
                    <td className={`py-1.5 px-2 font-medium ${trendColor(p.trend)}`}>{p.trend}</td>
                    <td className={`py-1.5 px-2 text-right font-mono tabular-nums font-medium ${p.yoy_growth >= 0 ? "text-reasoner-green" : "text-reasoner-red"}`}>
                      {p.yoy_growth >= 0 ? "+" : ""}{p.yoy_growth.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
