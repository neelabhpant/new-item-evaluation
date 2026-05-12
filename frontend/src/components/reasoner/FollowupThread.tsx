import { useEffect, useRef } from "react";
import { useFollowupSocket } from "../../hooks/useFollowupSocket";

interface Props {
  evaluationId: string;
  question: string;
  index: number;
}

/**
 * Renders a single follow-up: the user's question as an ink-bg card, then the
 * streaming agent answer below in Newsreader italic. Fires the API call on mount.
 */
export default function FollowupThread({ evaluationId, question, index }: Props) {
  const { text, status, errorMessage, ask } = useFollowupSocket();
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    ask(evaluationId, question);
  }, [evaluationId, question, ask]);

  return (
    <div className="mt-6 space-y-3">
      {/* User turn */}
      <div className="flex gap-3">
        <span className="text-[10px] font-mono tracking-[0.14em] text-reasoner-mute mt-2 shrink-0">
          USER · FOLLOW-UP {String(index + 1).padStart(2, "0")}
        </span>
        <div className="flex-1 p-3.5 rounded-lg bg-reasoner-ink text-reasoner-paper">
          <div className="text-[14.5px] leading-relaxed">{question}</div>
        </div>
      </div>

      {/* Agent answer */}
      <div className="p-4 rounded-lg border border-reasoner-accent-2 bg-reasoner-paper">
        <div className="flex items-center gap-2 mb-2">
          <span className="font-mono text-[10px] tracking-[0.1em] text-reasoner-mute">
            ▸ MERCHANDISING LEAD
          </span>
          {status === "running" && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-reasoner-accent-soft text-reasoner-accent tracking-[0.08em]">
              <span className="w-1.5 h-1.5 rounded-full bg-reasoner-accent" />
              thinking
            </span>
          )}
          {status === "complete" && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-reasoner-green/15 text-reasoner-green tracking-[0.08em]">
              done
            </span>
          )}
          {status === "error" && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-reasoner-red/15 text-reasoner-red tracking-[0.08em]">
              error
            </span>
          )}
        </div>

        {status === "error" ? (
          <p className="text-[13px] text-reasoner-red">{errorMessage ?? "Something went wrong."}</p>
        ) : (
          <p className="font-serif italic text-[15px] leading-relaxed text-reasoner-body whitespace-pre-wrap">
            {text}
            {status === "running" && (
              <span
                className="inline-block align-text-bottom ml-0.5 bg-reasoner-accent"
                style={{ width: "2px", height: "14px", animation: "dotPulse 1s infinite" }}
              />
            )}
          </p>
        )}
      </div>
    </div>
  );
}
