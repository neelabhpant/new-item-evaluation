import { useEffect, useState, type ReactNode } from "react";

export type ArtifactTone = "default" | "running" | "decline" | "authorize" | "modify";

interface Props {
  /** Small mono header label, e.g. "▸ VISUAL SIMILARITY" */
  agent: string;
  /** Optional title rendered below the header row */
  title?: string;
  /** Status pill next to the agent label */
  status?: "running" | "done" | "error";
  /** Elapsed time label, e.g. "2.1s" */
  elapsed?: string;
  /** Extra element rendered in the header (e.g. a custom badge) */
  headerAccessory?: ReactNode;
  /** Tone tunes the border color */
  tone?: ArtifactTone;
  /** Handoff to the next agent — renders an amber callout at the bottom */
  handoff?: { to: string; summary: string };
  /** One-line headline rendered when collapsed (Day 6) */
  summary?: string;
  /** DOM id for anchor/scroll targeting + data-pulsing (Day 6) */
  anchorId?: string;
  /** When false, the card is not collapsible. Defaults to true. Running/error cards never collapse. */
  collapsible?: boolean;
  children: ReactNode;
}

function StatusPill({ status }: { status: Props["status"] }) {
  if (!status) return null;
  const base = "px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold tracking-[0.08em]";
  if (status === "done") {
    return <span className={`${base} bg-reasoner-green/15 text-reasoner-green`}>done</span>;
  }
  if (status === "error") {
    return <span className={`${base} bg-reasoner-red/15 text-reasoner-red`}>error</span>;
  }
  return (
    <span
      className={`${base} bg-reasoner-accent-soft text-reasoner-accent inline-flex items-center gap-1`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-reasoner-accent" />
      running
    </span>
  );
}

function toneBorder(tone: ArtifactTone): string {
  if (tone === "running") return "border-reasoner-accent-2";
  if (tone === "decline") return "border-reasoner-red/40";
  if (tone === "authorize") return "border-reasoner-green/40";
  if (tone === "modify") return "border-reasoner-accent-2";
  return "border-reasoner-line";
}

export default function ArtifactCard({
  agent,
  title,
  status,
  elapsed,
  headerAccessory,
  tone = "default",
  handoff,
  summary,
  anchorId,
  collapsible = true,
  children,
}: Props) {
  const isRunning = tone === "running" || status === "running";
  const canCollapse = collapsible && !isRunning && status !== "error";

  const [expanded, setExpanded] = useState(true);

  // Whenever the parent-controlled status flips back to "running"/"error", force expand.
  useEffect(() => {
    if (!canCollapse) setExpanded(true);
  }, [canCollapse]);

  const toggle = () => {
    if (!canCollapse) return;
    setExpanded((v) => !v);
  };

  // ── Collapsed view: one-line pill ──
  if (canCollapse && !expanded) {
    return (
      <section
        id={anchorId}
        className={`relative overflow-hidden rounded-[10px] bg-reasoner-paper border ${toneBorder(tone)}`}
      >
        <button
          type="button"
          onClick={toggle}
          className="w-full flex items-center gap-3 px-4.5 py-3 text-left hover:bg-reasoner-accent-soft/30 transition-colors"
        >
          <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-reasoner-mute shrink-0">
            {agent}
          </span>
          <span className="text-[13px] text-reasoner-body truncate">
            {summary ?? title ?? ""}
          </span>
          <span className="flex-1" />
          {elapsed && (
            <span className="font-mono text-[10px] text-reasoner-dim shrink-0">{elapsed}</span>
          )}
          <span className="text-reasoner-mute shrink-0 text-[12px]">▸</span>
        </button>
      </section>
    );
  }

  // ── Expanded view ──
  return (
    <section
      id={anchorId}
      className={`relative overflow-hidden rounded-[10px] bg-reasoner-paper border ${toneBorder(tone)}`}
    >
      {isRunning && (
        <div
          className="absolute top-0 left-0 right-0 h-0.5 pointer-events-none"
          style={{
            background:
              "linear-gradient(90deg, transparent, var(--color-reasoner-accent), transparent)",
            backgroundSize: "200% 100%",
            animation: "shimmer 2.2s infinite",
          }}
        />
      )}

      <header
        className={`flex items-center gap-2.5 px-4.5 py-3 border-b border-reasoner-line ${
          canCollapse ? "cursor-pointer hover:bg-reasoner-bg/50 transition-colors" : ""
        }`}
        onClick={toggle}
      >
        <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-reasoner-mute">
          {agent}
        </span>
        <StatusPill status={status} />
        {headerAccessory}
        <span className="flex-1" />
        {elapsed && (
          <span className="font-mono text-[10px] text-reasoner-dim">{elapsed}</span>
        )}
        {canCollapse && (
          <span
            className="text-reasoner-mute text-[12px] transition-transform"
            style={{ transform: "rotate(90deg)" }}
            aria-hidden="true"
          >
            ▸
          </span>
        )}
      </header>

      <div className="p-[18px]">
        {title && (
          <h3 className="text-[17px] font-semibold text-reasoner-ink mb-3.5">
            {title}
          </h3>
        )}
        {children}

        {handoff && (
          <div className="mt-3.5 px-3.5 py-2.5 rounded bg-reasoner-accent-soft border-l-[3px] border-reasoner-accent">
            <p className="font-mono text-[11px] font-semibold tracking-wide text-reasoner-accent mb-1">
              ↻ HANDOFF → {handoff.to}
            </p>
            <p className="text-[13px] text-reasoner-body">{handoff.summary}</p>
          </div>
        )}
      </div>
    </section>
  );
}
