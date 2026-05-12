export type AgentState = "idle" | "running" | "done";

export interface AgentSpec {
  id: "risk" | "fin" | "synth";
  name: string;
  role: string;
}

export const AGENTS: AgentSpec[] = [
  {
    id: "risk",
    name: "Risk & Market Analyst",
    role: "Analyzes cannibalization, market timing, category context across the catalog.",
  },
  {
    id: "fin",
    name: "Financial Projector",
    role: "Builds best/expected/worst Year 1 revenue, margin, vendor relationship risk.",
  },
  {
    id: "synth",
    name: "Merchandising Lead",
    role: "Synthesizes into AUTHORIZE/MODIFY/DECLINE with confidence and evidence.",
  },
];

interface Props {
  states?: Partial<Record<AgentSpec["id"], AgentState>>;
  elapsed?: Partial<Record<AgentSpec["id"], string>>;
  onJumpTo?: (agentId: AgentSpec["id"]) => void;
}

function headerLabel(states: Partial<Record<AgentSpec["id"], AgentState>>): string {
  const vals = AGENTS.map((a) => states[a.id] ?? "idle");
  if (vals.every((v) => v === "idle")) return "AGENTS · IDLE";
  if (vals.every((v) => v === "done")) return "AGENTS · COMPLETE";
  return "AGENTS · REASONING";
}

export default function AgentRail({ states = {}, elapsed = {}, onJumpTo }: Props) {
  return (
    <div className="flex flex-col gap-3">
      <div className="text-[11px] font-mono text-reasoner-mute tracking-[0.12em] mb-1">
        {headerLabel(states)}
      </div>
      {AGENTS.map((a, i) => {
        const state: AgentState = states[a.id] ?? "idle";
        const done = state === "done";
        const running = state === "running";
        const jumpable = done && typeof onJumpTo === "function";

        const handleClick = jumpable ? () => onJumpTo!(a.id) : undefined;
        const handleKeyDown = jumpable
          ? (e: React.KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onJumpTo!(a.id);
              }
            }
          : undefined;

        return (
          <div
            key={a.id}
            role={jumpable ? "button" : undefined}
            tabIndex={jumpable ? 0 : undefined}
            onClick={handleClick}
            onKeyDown={handleKeyDown}
            className={`relative overflow-hidden rounded-lg p-3.5 border transition-colors ${
              running
                ? "bg-reasoner-accent-soft border-reasoner-accent-2"
                : "bg-reasoner-paper border-reasoner-line"
            } ${
              jumpable
                ? "cursor-pointer hover:border-reasoner-accent hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-reasoner-accent/40"
                : ""
            }`}
          >
            {running && (
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, rgba(234,88,12,0.10), transparent)",
                  backgroundSize: "200% 100%",
                  animation: "shimmer 2.2s infinite",
                }}
              />
            )}
            <div className="relative flex items-center gap-2.5">
              <div
                className={`w-8 h-8 rounded-lg grid place-items-center text-sm font-semibold font-mono flex-shrink-0 ${
                  done
                    ? "bg-reasoner-green text-reasoner-paper"
                    : running
                    ? "bg-reasoner-accent text-reasoner-paper"
                    : "bg-reasoner-line text-reasoner-mute"
                }`}
              >
                {done ? "✓" : String(i + 1)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-reasoner-ink">{a.name}</div>
                <div className="text-[11px] text-reasoner-mute mt-0.5 leading-snug">{a.role}</div>
              </div>
              {jumpable && (
                <span
                  className="text-reasoner-mute text-[14px] shrink-0"
                  aria-hidden="true"
                  title="Jump to artifact"
                >
                  ↗
                </span>
              )}
            </div>
            {running && (
              <div className="relative mt-2.5 flex items-center gap-1">
                {[0, 1, 2].map((n) => (
                  <span
                    key={n}
                    className="w-1.5 h-1.5 rounded-full bg-reasoner-accent"
                    style={{
                      animation: "dotPulse 1.4s infinite",
                      animationDelay: `${n * 0.2}s`,
                    }}
                  />
                ))}
                <span className="ml-1 text-[11px] font-mono text-reasoner-accent">thinking</span>
              </div>
            )}
            {done && (
              <div className="relative mt-2 text-[11px] font-mono text-reasoner-green">
                ✓ done {elapsed[a.id] ? `· ${elapsed[a.id]}` : ""}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
