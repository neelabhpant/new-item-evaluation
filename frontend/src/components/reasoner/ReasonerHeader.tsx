type TabId = "evaluate" | "catalog" | "history" | "merchant" | "supplier" | "batch";

interface Props {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  evaluationId?: string | null;
}

const TABS: { id: TabId; label: string; kbd: string }[] = [
  { id: "evaluate", label: "Evaluate",        kbd: "⌘1" },
  { id: "catalog",  label: "Catalog",         kbd: "⌘2" },
  { id: "merchant", label: "Merchant Queue",  kbd: "⌘3" },
  { id: "supplier", label: "Supplier Portal", kbd: "⌘4" },
  { id: "batch",    label: "Batch",           kbd: "⌘5" },
  { id: "history",  label: "History",         kbd: "⌘6" },
];

export default function ReasonerHeader({ activeTab, onTabChange, evaluationId }: Props) {
  const currentLabel = TABS.find((t) => t.id === activeTab)?.label ?? "Evaluate";

  return (
    <header className="bg-reasoner-paper border-b border-reasoner-line font-sans">
      <div className="flex items-center gap-5 px-7 h-[58px]">
        <div className="flex items-center gap-2.5">
          <div className="w-[26px] h-[26px] bg-reasoner-ink text-reasoner-paper rounded-md grid place-items-center text-sm font-semibold">
            N
          </div>
          <div className="text-sm font-semibold text-reasoner-ink">NIE</div>
          <span className="text-xs text-reasoner-dim">/</span>
          <div className="text-[13px] text-reasoner-body">{currentLabel}</div>
          {evaluationId && (
            <>
              <span className="text-xs text-reasoner-dim">/</span>
              <div className="text-[13px] text-reasoner-mute font-mono">{evaluationId}</div>
            </>
          )}
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2 px-3 py-1.5 bg-reasoner-bg border border-reasoner-line rounded-md w-[360px] text-[13px] text-reasoner-mute font-mono">
          <span className="text-reasoner-dim">⌘K</span>
          <span>Ask anything, or find a product…</span>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2.5 text-xs text-reasoner-mute">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-reasoner-green" />
          <span>Cloudera AI · 3 agents online</span>
        </div>
      </div>

      <nav className="flex px-7 border-t border-reasoner-line">
        {TABS.map((t) => {
          const on = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onTabChange(t.id)}
              className={`px-4 py-2.5 flex items-center gap-2 -mb-px border-b-2 text-[13px] transition-colors ${
                on
                  ? "border-reasoner-accent text-reasoner-ink font-medium"
                  : "border-transparent text-reasoner-mute hover:text-reasoner-ink"
              }`}
            >
              <span>{t.label}</span>
              <span className="font-mono text-[10px] text-reasoner-dim">{t.kbd}</span>
            </button>
          );
        })}
      </nav>
    </header>
  );
}
