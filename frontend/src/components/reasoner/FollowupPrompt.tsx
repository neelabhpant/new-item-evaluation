import { useState, type FormEvent } from "react";
import FollowupThread from "./FollowupThread";

interface Props {
  evaluationId: string | null;
  productName?: string;
}

const CHIPS: { question: string; meta: string }[] = [
  {
    question: "What would flip this to MODIFY?",
    meta: "explores alternative replacement sets",
  },
  {
    question: "Which vendor is most at risk?",
    meta: "breakdown of cannibalization by supplier",
  },
  {
    question: "Compare against the last 3 rejections in this category.",
    meta: "pulls recent DECLINE patterns for context",
  },
];

interface SubmittedFollowup {
  id: number;
  question: string;
}

export default function FollowupPrompt({ evaluationId, productName }: Props) {
  const [input, setInput] = useState("");
  const [submitted, setSubmitted] = useState<SubmittedFollowup[]>([]);

  if (!evaluationId) return null;

  const submit = (question: string) => {
    const q = question.trim();
    if (!q) return;
    setSubmitted((prev) => [...prev, { id: Date.now(), question: q }]);
    setInput("");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(input);
  };

  return (
    <div className="mt-6 space-y-4">
      <div className="p-5 rounded-xl border border-reasoner-line bg-reasoner-paper">
        <div className="text-[10px] font-mono tracking-[0.14em] text-reasoner-mute mb-2">
          ASK A FOLLOW-UP
        </div>
        <p className="text-[13.5px] text-reasoner-body leading-relaxed mb-4">
          The three agents hold the context for this evaluation
          {productName ? (
            <>
              {", "}<strong className="text-reasoner-ink font-semibold">{productName}</strong>
            </>
          ) : null}
          . Ask anything about this submission, or pick a scoped suggestion:
        </p>

        <div className="flex flex-wrap gap-2 mb-4">
          {CHIPS.map((c) => (
            <button
              key={c.question}
              type="button"
              onClick={() => submit(c.question)}
              className="flex flex-col items-start text-left max-w-md px-4 py-2.5 rounded-full bg-reasoner-bg border border-reasoner-line hover:border-reasoner-accent hover:bg-reasoner-accent-soft/30 transition-colors"
            >
              <span className="text-[13.5px] text-reasoner-ink font-medium leading-snug">
                {c.question}
              </span>
              <span className="text-[10.5px] font-mono text-reasoner-mute mt-0.5">
                {c.meta}
              </span>
            </button>
          ))}
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-3 p-3 rounded-lg bg-reasoner-bg border border-reasoner-line-2"
        >
          <span className="font-mono text-[11px] text-reasoner-mute px-2 py-1 bg-reasoner-paper border border-reasoner-line rounded">
            @
          </span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this evaluation…"
            className="flex-1 bg-transparent border-none outline-none text-[14px] text-reasoner-body placeholder:text-reasoner-dim"
          />
          <span className="font-mono text-[10.5px] text-reasoner-mute">
            {evaluationId.slice(0, 8)} in context
          </span>
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-3.5 py-1.5 text-[13px] font-semibold text-reasoner-paper bg-reasoner-accent rounded-md hover:bg-reasoner-accent-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Ask
          </button>
        </form>

        <p className="mt-2.5 text-[11px] font-mono text-reasoner-dim">
          Follow-ups re-use the existing 3 agents and cached tool outputs from this evaluation. No new agents are spawned.
        </p>
      </div>

      {submitted.map((f, i) => (
        <FollowupThread key={f.id} evaluationId={evaluationId} question={f.question} index={i} />
      ))}
    </div>
  );
}
