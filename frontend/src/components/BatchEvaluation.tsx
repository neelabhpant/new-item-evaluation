import { useCallback, useRef, useState } from "react";
import PortfolioMatrix from "./PortfolioMatrix";

interface ProductRow {
  id: string;
  name: string;
  description: string;
  price: string;
  category: string;
  claims: string;
  image_path: string;
}

interface BatchResult {
  index: number;
  name: string;
  result_preview?: string;
  error?: string;
}

interface BatchMessage {
  type: string;
  index?: number;
  total?: number;
  product_name?: string;
  result_preview?: string;
  error?: string;
  results?: BatchResult[];
  similarity_matrix?: number[][];
}

const EMPTY_ROW = (): ProductRow => ({
  id: crypto.randomUUID(),
  name: "",
  description: "",
  price: "",
  category: "Auto-detect",
  claims: "",
  image_path: "",
});

const CATEGORIES = [
  "Auto-detect",
  "Protein Bars", "Energy Bars", "Granola Bars", "Nut Bars", "Snack Bars",
  "Chocolate & Candy", "Cookies", "Chips", "Potato Chips", "Tortilla Chips",
  "Veggie Snacks", "Popcorn", "Crackers", "Rice Cakes", "Pretzels",
  "Trail Mix", "Fruit Snacks", "Cheese Snacks", "Puffed Snacks", "Other Snacks",
];

const INPUT_CLASS =
  "px-2 py-1.5 text-xs bg-reasoner-paper border border-reasoner-line rounded text-reasoner-ink placeholder:text-reasoner-dim focus:outline-none focus:ring-2 focus:ring-reasoner-accent/30 focus:border-reasoner-accent";

export default function BatchEvaluation() {
  const [rows, setRows] = useState<ProductRow[]>([EMPTY_ROW(), EMPTY_ROW(), EMPTY_ROW()]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Map<number, string>>(new Map());
  const [results, setResults] = useState<BatchResult[]>([]);
  const [matrix, setMatrix] = useState<number[][] | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const updateRow = useCallback((id: string, field: keyof ProductRow, value: string) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  }, []);

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, EMPTY_ROW()]);
  }, []);

  const removeRow = useCallback((id: string) => {
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((r) => r.id !== id)));
  }, []);

  const handleSubmit = useCallback(async () => {
    const valid = rows.filter((r) => r.name.trim() && r.image_path.trim());
    if (valid.length === 0) return;

    setRunning(true);
    setResults([]);
    setMatrix(null);
    setProgress(new Map());

    const resp = await fetch("/api/evaluate/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        products: valid.map((r) => ({
          name: r.name,
          description: r.description,
          price: parseFloat(r.price) || 0,
          category: r.category,
          claims: r.claims,
          image_path: r.image_path,
        })),
      }),
    });

    const { batch_id } = await resp.json();
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/batch/${batch_id}`);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      const msg: BatchMessage = JSON.parse(evt.data);

      if (msg.type === "product_start") {
        setProgress((prev) => {
          const next = new Map(prev);
          next.set(msg.index!, "running");
          return next;
        });
      } else if (msg.type === "product_complete") {
        setProgress((prev) => {
          const next = new Map(prev);
          next.set(msg.index!, "complete");
          return next;
        });
      } else if (msg.type === "product_error") {
        setProgress((prev) => {
          const next = new Map(prev);
          next.set(msg.index!, "error");
          return next;
        });
      } else if (msg.type === "batch_done") {
        setResults(msg.results ?? []);
        setMatrix(msg.similarity_matrix && msg.similarity_matrix.length > 0 ? msg.similarity_matrix : null);
        setRunning(false);
      }
    };

    ws.onerror = () => setRunning(false);
  }, [rows]);

  const validCount = rows.filter((r) => r.name.trim() && r.image_path.trim()).length;

  return (
    <div className="flex-1 p-6 bg-reasoner-bg">
      <div className="max-w-[1200px] mx-auto space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-reasoner-ink">Batch Portfolio Evaluation</h2>
          <p className="text-xs text-reasoner-mute mt-0.5">
            Submit multiple products at once. After evaluation, see pairwise similarity to detect intra-portfolio cannibalization.
          </p>
        </div>

        {/* Product input rows */}
        <div className="bg-reasoner-paper rounded-lg border border-reasoner-line">
          <div className="px-5 py-3 border-b border-reasoner-line flex items-center justify-between">
            <h3 className="text-sm font-semibold text-reasoner-ink">
              Products <span className="font-mono tabular-nums text-reasoner-mute font-normal">({rows.length})</span>
            </h3>
            <button
              onClick={addRow}
              className="text-xs text-reasoner-accent hover:text-reasoner-accent-2 font-semibold"
            >
              + Add Product
            </button>
          </div>
          <div className="divide-y divide-reasoner-line/60">
            {rows.map((row, idx) => (
              <div key={row.id} className="px-5 py-3 flex gap-3 items-start">
                <div className="w-6 pt-2 text-xs font-mono tabular-nums text-reasoner-dim font-medium">{idx + 1}</div>
                <div className="flex-1 grid grid-cols-6 gap-2">
                  <input
                    placeholder="Product name *"
                    value={row.name}
                    onChange={(e) => updateRow(row.id, "name", e.target.value)}
                    className={`col-span-2 ${INPUT_CLASS}`}
                  />
                  <input
                    placeholder="Description"
                    value={row.description}
                    onChange={(e) => updateRow(row.id, "description", e.target.value)}
                    className={`col-span-2 ${INPUT_CLASS}`}
                  />
                  <input
                    placeholder="Price"
                    type="number"
                    step="0.01"
                    value={row.price}
                    onChange={(e) => updateRow(row.id, "price", e.target.value)}
                    className={`${INPUT_CLASS} font-mono tabular-nums`}
                  />
                  <select
                    value={row.category}
                    onChange={(e) => updateRow(row.id, "category", e.target.value)}
                    className={INPUT_CLASS}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                  <input
                    placeholder="Claims (comma-separated)"
                    value={row.claims}
                    onChange={(e) => updateRow(row.id, "claims", e.target.value)}
                    className={`col-span-3 ${INPUT_CLASS}`}
                  />
                  <input
                    placeholder="Image path *"
                    value={row.image_path}
                    onChange={(e) => updateRow(row.id, "image_path", e.target.value)}
                    className={`col-span-2 ${INPUT_CLASS} font-mono`}
                  />
                  <button
                    onClick={() => removeRow(row.id)}
                    className="px-2 py-1.5 text-xs font-medium text-reasoner-red/70 hover:text-reasoner-red"
                    title="Remove"
                  >
                    Remove
                  </button>
                </div>
                {/* Progress indicator */}
                {running && (
                  <div className="w-6 pt-2">
                    {progress.get(idx) === "running" && (
                      <div className="w-4 h-4 border-2 border-reasoner-accent border-t-transparent rounded-full animate-spin" />
                    )}
                    {progress.get(idx) === "complete" && (
                      <svg className="w-4 h-4 text-reasoner-green" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                    {progress.get(idx) === "error" && (
                      <svg className="w-4 h-4 text-reasoner-red" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="px-5 py-3 border-t border-reasoner-line">
            <button
              onClick={handleSubmit}
              disabled={running || validCount === 0}
              className="px-5 py-2 bg-reasoner-accent text-reasoner-paper text-sm font-semibold rounded-md hover:bg-reasoner-accent-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {running ? "Evaluating…" : `Evaluate ${validCount} Product${validCount !== 1 ? "s" : ""}`}
            </button>
          </div>
        </div>

        {/* Results */}
        {results.length > 0 && (
          <div className="bg-reasoner-paper rounded-lg border border-reasoner-line">
            <div className="px-5 py-3 border-b border-reasoner-line">
              <h3 className="text-sm font-semibold text-reasoner-ink">Batch Results</h3>
            </div>
            <div className="divide-y divide-reasoner-line/60">
              {results.map((r) => (
                <div key={r.index} className="px-5 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm text-reasoner-ink">{r.name}</span>
                    {r.error ? (
                      <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-red-50 text-reasoner-red rounded-full tracking-[0.05em]">
                        ERROR
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-reasoner-green/15 text-reasoner-green rounded-full tracking-[0.05em]">
                        COMPLETE
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-reasoner-body whitespace-pre-wrap max-h-32 overflow-y-auto font-mono">
                    {r.error || r.result_preview}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Portfolio similarity matrix */}
        {matrix && (
          <PortfolioMatrix
            matrix={matrix}
            names={results.map((r) => r.name)}
          />
        )}
      </div>
    </div>
  );
}
