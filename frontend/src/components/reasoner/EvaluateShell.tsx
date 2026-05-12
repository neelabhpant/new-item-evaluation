import type { ReactNode } from "react";
import AgentRail, { type AgentState, type AgentSpec } from "./AgentRail";

interface Props {
  children: ReactNode;
  agentStates?: Partial<Record<AgentSpec["id"], AgentState>>;
  agentElapsed?: Partial<Record<AgentSpec["id"], string>>;
  onJumpTo?: (agentId: AgentSpec["id"]) => void;
}

export default function EvaluateShell({ children, agentStates, agentElapsed, onJumpTo }: Props) {
  return (
    <div className="flex-1 bg-reasoner-bg min-h-0">
      <div className="grid grid-cols-[280px_1fr] min-h-full">
        <aside className="border-r border-reasoner-line bg-reasoner-paper p-5">
          <AgentRail states={agentStates} elapsed={agentElapsed} onJumpTo={onJumpTo} />
        </aside>
        <main className="p-8 min-w-0">{children}</main>
      </div>
    </div>
  );
}
