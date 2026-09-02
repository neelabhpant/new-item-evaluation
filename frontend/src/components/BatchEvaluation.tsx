import { useCallback, useEffect, useRef, useState } from "react";
import PortfolioMatrix from "./PortfolioMatrix";

interface ProductRow {
  id: string;
  name: string;
  description: string;
  price: string;
  category: string;
  claims: string;
  image_preview: string | null;
  image_base64: string | null;
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
  image_preview: null,
  image_base64: null,
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

interface ImageDropProps {
  preview: string | null;
  onFile: (file: File) => void;
}

function ImageDrop({ preview, onFile }: ImageDropProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!dragActive) setDragActive(true);
      }}
      onDragEnter={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!dragActive) setDragActive(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        const file = e.dataTransfer.files?.[0];
        if (file && file.type.startsWith("image/")) onFile(file);
      }}
      className={`w-12 h-12 border-2 border-dashed rounded cursor-pointer flex items-center justify-center overflow-hidden transition-colors shrink-0 ${
        dragActive
          ? "border-reasoner-accent bg-reasoner-accent/10"
          : preview
            ? "border-reasoner-line"
            : "border-reasoner-line hover:border-reasoner-accent"
      }`}
      title={preview ? "Click to replace image" : "Drop image or click to upload"}
    >
      {preview ? (
        <img src={preview} alt="" className="w-full h-full object-cover pointer-events-none" />
      ) : (
        <svg className="w-5 h-5 text-reasoner-dim pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.41a2.25 2.25 0 013.182 0l2.909 2.91m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5z" />
        </svg>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
      />
    </div>
  );
}

function extractField(text: string, field: string): string {
  const m = text.match(new RegExp(`${field}:\\s*(.+?)(?:\\n|$)`));
  return m ? m[1].trim() : "";
}

interface BatchResultRowProps {
  result: BatchResult;
}

function BatchResultRow({ result }: BatchResultRowProps) {
  const [expanded, setExpanded] = useState(false);

  if (result.error) {
    return (
      <div className="px-5 py-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm text-reasoner-ink">{result.name}</span>
          <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-red-50 text-reasoner-red rounded-full tracking-[0.05em]">
            ERROR
          </span>
        </div>
        <p className="text-xs text-reasoner-red font-mono">{result.error}</p>
      </div>
    );
  }

  const text = result.result_preview || "";
  const verdict = extractField(text, "VERDICT") || "—";
  const confidence = extractField(text, "CONFIDENCE") || "";
  const reasons = [
    extractField(text, "REASON_1"),
    extractField(text, "REASON_2"),
    extractField(text, "REASON_3"),
  ].filter(Boolean);
  const suggestedRetail = extractField(text, "SUGGESTED_RETAIL");
  const placement = extractField(text, "PLACEMENT");
  const rollout = extractField(text, "ROLLOUT");
  const replaceSkus = extractField(text, "REPLACE_SKUS");

  const verdictColor =
    verdict === "AUTHORIZE"
      ? "bg-reasoner-green/15 text-reasoner-green"
      : verdict === "DECLINE"
        ? "bg-red-50 text-reasoner-red"
        : verdict === "MODIFY"
          ? "bg-amber-50 text-amber-700"
          : "bg-gray-100 text-gray-600";

  return (
    <div className="px-5 py-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 text-left"
      >
        <span className="font-medium text-sm text-reasoner-ink flex-1">{result.name}</span>
        <span className={`px-2 py-0.5 text-[10px] font-mono font-semibold rounded-full tracking-[0.05em] ${verdictColor}`}>
          {verdict}
        </span>
        {confidence && (
          <span className="text-xs font-mono tabular-nums text-reasoner-mute">{confidence}</span>
        )}
        <svg
          className={`w-4 h-4 text-reasoner-dim transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-3 pl-1 space-y-2 text-xs text-reasoner-body">
          {reasons.length > 0 && (
            <ol className="space-y-1 list-decimal list-inside marker:text-reasoner-dim marker:font-mono">
              {reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ol>
          )}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-2 text-[11px]">
            {suggestedRetail && suggestedRetail !== "N/A" && (
              <div>
                <span className="text-reasoner-mute">Suggested retail: </span>
                <span className="font-mono tabular-nums text-reasoner-ink">{suggestedRetail}</span>
              </div>
            )}
            {placement && placement !== "N/A" && (
              <div>
                <span className="text-reasoner-mute">Placement: </span>
                <span className="text-reasoner-ink">{placement}</span>
              </div>
            )}
            {rollout && rollout !== "N/A" && (
              <div>
                <span className="text-reasoner-mute">Rollout: </span>
                <span className="text-reasoner-ink">{rollout}</span>
              </div>
            )}
            {replaceSkus && replaceSkus !== "NONE" && (
              <div className="col-span-2">
                <span className="text-reasoner-mute">Replace SKUs: </span>
                <span className="text-reasoner-ink">{replaceSkus}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BatchEvaluation() {
  const [rows, setRows] = useState<ProductRow[]>([EMPTY_ROW(), EMPTY_ROW(), EMPTY_ROW()]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Map<number, string>>(new Map());
  const [results, setResults] = useState<BatchResult[]>([]);
  const [matrix, setMatrix] = useState<number[][] | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Prevent the browser from navigating if the user drops a file outside a drop zone
  useEffect(() => {
    const block = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  const updateRow = useCallback((id: string, field: keyof ProductRow, value: string | null) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  }, []);

  const setRowImage = useCallback((id: string, file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      setRows((prev) =>
        prev.map((r) =>
          r.id === id ? { ...r, image_preview: result, image_base64: base64 } : r,
        ),
      );
    };
    reader.readAsDataURL(file);
  }, []);

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, EMPTY_ROW()]);
  }, []);

  const removeRow = useCallback((id: string) => {
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((r) => r.id !== id)));
  }, []);

  const handleSubmit = useCallback(async () => {
    const valid = rows.filter((r) => r.name.trim() && r.image_base64);
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
          image: r.image_base64,
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

  const validCount = rows.filter((r) => r.name.trim() && r.image_base64).length;

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
                <div className="w-6 pt-3 text-xs font-mono tabular-nums text-reasoner-dim font-medium">{idx + 1}</div>
                <ImageDrop
                  preview={row.image_preview}
                  onFile={(file) => setRowImage(row.id, file)}
                />
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
                    className={`col-span-5 ${INPUT_CLASS}`}
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
                  <div className="w-6 pt-3">
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
          <div className="px-5 py-3 border-t border-reasoner-line flex items-center justify-between">
            <p className="text-xs text-reasoner-dim">
              Drop an image into each row's thumbnail box, or click it to browse. Name + image required per row.
            </p>
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
                <BatchResultRow key={r.index} result={r} />
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
