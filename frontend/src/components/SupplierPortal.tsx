import { useCallback, useEffect, useState } from "react";

interface Submission {
  id: string;
  timestamp: string;
  product_name: string;
  brand: string;
  category: string;
  price: number;
  claims: string;
  verdict: string;
  confidence: number;
}

function verdictFeedback(verdict: string): { label: string; color: string; message: string } {
  switch (verdict.toUpperCase()) {
    case "AUTHORIZE":
      return {
        label: "Approved",
        color: "bg-reasoner-green/15 text-reasoner-green border-reasoner-green/30",
        message: "Your product has been approved for the retailer's assortment.",
      };
    case "DECLINE":
      return {
        label: "Not Approved",
        color: "bg-red-50 text-reasoner-red border-red-200",
        message: "Your product was not approved at this time. Consider revising and resubmitting.",
      };
    case "MODIFY":
      return {
        label: "Revisions Requested",
        color: "bg-amber-50 text-amber-700 border-amber-200",
        message: "The review team has suggested modifications before approval.",
      };
    default:
      return {
        label: "Under Review",
        color: "bg-reasoner-line/50 text-reasoner-mute border-reasoner-line",
        message: "Your submission is being evaluated.",
      };
  }
}

function formatDate(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return ts;
  }
}

export default function SupplierPortal() {
  const [brandFilter, setBrandFilter] = useState("");
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const fetchSubmissions = useCallback(() => {
    if (!brandFilter.trim()) return;
    setLoading(true);
    setSearched(true);
    fetch("/api/evaluations?limit=100")
      .then((r) => r.json())
      .then((all: Submission[]) => {
        const filtered = all.filter(
          (e) => e.brand.toLowerCase().includes(brandFilter.trim().toLowerCase())
        );
        setSubmissions(filtered);
      })
      .catch(() => setSubmissions([]))
      .finally(() => setLoading(false));
  }, [brandFilter]);

  useEffect(() => {
    // Load all on mount for demo purposes
    fetch("/api/evaluations?limit=100")
      .then((r) => r.json())
      .then(setSubmissions)
      .catch(() => {});
  }, []);

  return (
    <div className="flex-1 p-6 bg-reasoner-bg">
      <div className="max-w-[900px] mx-auto space-y-6">
        {/* Hero section */}
        <div className="bg-reasoner-accent-soft border border-reasoner-accent-2/40 rounded-lg p-6">
          <div className="text-[10px] font-mono tracking-[0.14em] text-reasoner-accent mb-2">
            SUPPLIER PORTAL
          </div>
          <h2 className="text-lg font-semibold text-reasoner-ink">Submit products. Track outcomes.</h2>
          <p className="text-sm text-reasoner-body mt-1">
            Submit your products for evaluation and track their review status.
            Use the "Evaluate" tab to submit a new product.
          </p>
        </div>

        {/* Brand filter */}
        <div className="bg-reasoner-paper rounded-lg border border-reasoner-line p-5">
          <h3 className="text-sm font-semibold text-reasoner-ink mb-3">Find My Submissions</h3>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Enter your brand name…"
              value={brandFilter}
              onChange={(e) => setBrandFilter(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchSubmissions()}
              className="flex-1 px-3 py-2 text-sm bg-reasoner-paper border border-reasoner-line rounded-md text-reasoner-ink placeholder:text-reasoner-dim focus:outline-none focus:ring-2 focus:ring-reasoner-accent/30 focus:border-reasoner-accent"
            />
            <button
              onClick={fetchSubmissions}
              className="px-4 py-2 bg-reasoner-accent text-reasoner-paper text-sm font-semibold rounded-md hover:bg-reasoner-accent-2 transition-colors"
            >
              Search
            </button>
          </div>
        </div>

        {/* Submissions list */}
        <div className="bg-reasoner-paper rounded-lg border border-reasoner-line">
          <div className="px-5 py-3 border-b border-reasoner-line">
            <h3 className="text-sm font-semibold text-reasoner-ink">
              {searched && brandFilter.trim()
                ? `Submissions for "${brandFilter.trim()}"`
                : "All Recent Submissions"}
            </h3>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-reasoner-mute font-mono">LOADING…</div>
          ) : submissions.length === 0 ? (
            <div className="p-8 text-center text-sm text-reasoner-mute">
              {searched
                ? "No submissions found for this brand."
                : "No submissions yet."}
            </div>
          ) : (
            <div className="divide-y divide-reasoner-line/60">
              {submissions.map((sub) => {
                const fb = verdictFeedback(sub.verdict);
                return (
                  <div key={sub.id} className="px-5 py-4">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="font-medium text-sm text-reasoner-ink">{sub.product_name}</div>
                        <div className="text-xs text-reasoner-mute font-mono mt-0.5">
                          {sub.category} · ${sub.price.toFixed(2)} · Submitted {formatDate(sub.timestamp)}
                        </div>
                      </div>
                      <span
                        className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold border tracking-[0.05em] ${fb.color}`}
                      >
                        {fb.label}
                      </span>
                    </div>
                    <p className="text-xs text-reasoner-body">{fb.message}</p>
                    {sub.claims && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {sub.claims.split(",").map((c) => (
                          <span
                            key={c}
                            className="px-2 py-0.5 bg-reasoner-bg text-reasoner-mute text-[10px] rounded-full border border-reasoner-line"
                          >
                            {c.trim()}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
