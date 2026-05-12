import type { EnrichedProduct } from "../types";
import ArtifactCard from "./reasoner/ArtifactCard";

interface Props {
  products: EnrichedProduct[];
  submittedName?: string;
  suggestedPosition?: string;
}

const SHELF_ROWS: { key: string; label: string }[] = [
  { key: "top", label: "Top Shelf" },
  { key: "eye-level", label: "Eye Level" },
  { key: "bottom", label: "Bottom Shelf" },
  { key: "endcap", label: "Endcap" },
];

function positionLabel(pos: string): string {
  switch (pos) {
    case "eye-level": return "Eye Level";
    case "top": return "Top Shelf";
    case "bottom": return "Bottom Shelf";
    case "endcap": return "Endcap";
    default: return pos;
  }
}

export default function PlanogramView({ products, submittedName, suggestedPosition = "eye-level" }: Props) {
  if (!products || products.length === 0) return null;

  const grouped: Record<string, EnrichedProduct[]> = {
    top: [],
    "eye-level": [],
    bottom: [],
    endcap: [],
  };

  for (const p of products) {
    const pos = p.shelf_position || "bottom";
    if (grouped[pos]) {
      grouped[pos].push(p);
    } else {
      grouped.bottom.push(p);
    }
  }

  const headerAccessory = submittedName ? (
    <div className="flex items-center gap-1.5 text-[10px] font-mono text-reasoner-mute tracking-[0.05em]">
      <span className="w-2.5 h-2.5 rounded border-2 border-dashed border-reasoner-accent" />
      <span>Suggested: <span className="text-reasoner-accent">{submittedName}</span></span>
    </div>
  ) : null;

  const totalProducts = Object.values(grouped).reduce((sum, arr) => sum + arr.length, 0);
  const planogramSummary =
    `Recommended: ${positionLabel(suggestedPosition)} · ${totalProducts} competing products placed`;

  return (
    <ArtifactCard
      agent="▸ SHELF PLANOGRAM"
      status="done"
      title="Current competitor placement + recommended position"
      headerAccessory={headerAccessory}
      summary={planogramSummary}
    >
      <div className="space-y-1.5">
        {SHELF_ROWS.map((row) => {
          const items = grouped[row.key] || [];
          const isTarget = row.key === suggestedPosition;

          return (
            <div
              key={row.key}
              className={`flex items-stretch rounded-md overflow-hidden ${
                isTarget
                  ? "bg-reasoner-accent-soft border border-reasoner-accent-2"
                  : "bg-reasoner-bg border border-reasoner-line"
              }`}
            >
              <div className="w-24 shrink-0 flex items-center justify-center border-r border-reasoner-line px-2">
                <span
                  className={`text-[10px] font-mono font-semibold tracking-[0.08em] ${
                    isTarget ? "text-reasoner-accent" : "text-reasoner-mute"
                  }`}
                >
                  {row.label.toUpperCase()}
                </span>
              </div>

              <div className="flex-1 flex items-center gap-2 p-2 min-h-[64px] overflow-x-auto">
                {isTarget && submittedName && (
                  <div
                    className="w-12 h-12 rounded border-2 border-dashed border-reasoner-accent bg-reasoner-paper/80 flex items-center justify-center shrink-0"
                    title={submittedName}
                  >
                    <span className="text-[9px] font-mono font-bold text-reasoner-accent text-center leading-tight tracking-wider">
                      NEW
                    </span>
                  </div>
                )}

                {items.map((p) => {
                  const imgFile = p.image_path?.split("/").pop() || "";
                  return (
                    <div
                      key={p.sku}
                      className="w-12 h-12 rounded border border-reasoner-line bg-reasoner-paper overflow-hidden shrink-0 relative group"
                      title={`${p.name} (${p.brand}) · ${(p.similarity_score * 100).toFixed(0)}% similar`}
                    >
                      {imgFile ? (
                        <img
                          src={`/api/images/${imgFile}`}
                          alt={p.name}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[8px] text-reasoner-dim font-mono">
                          —
                        </div>
                      )}
                      <div className="absolute inset-0 bg-reasoner-ink/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span className="text-[9px] font-mono tabular-nums text-reasoner-paper font-bold">
                          {(p.similarity_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  );
                })}

                {items.length === 0 && !isTarget && (
                  <span className="text-[10px] text-reasoner-dim italic">No products on this shelf</span>
                )}
              </div>

              <div className="w-12 shrink-0 flex items-center justify-center border-l border-reasoner-line">
                <span className="text-[11px] font-mono tabular-nums text-reasoner-mute">
                  {items.length + (isTarget && submittedName ? 1 : 0)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-4 mt-3 text-[10px] font-mono text-reasoner-mute">
        <span>Hover over products to see similarity scores.</span>
        {suggestedPosition && (
          <span>
            Recommended placement:{" "}
            <strong className="text-reasoner-accent font-semibold">
              {positionLabel(suggestedPosition)}
            </strong>
          </span>
        )}
      </div>
    </ArtifactCard>
  );
}
