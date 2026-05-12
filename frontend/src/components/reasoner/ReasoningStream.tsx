import { useEffect, useRef, useState } from "react";

interface Props {
  /** Full text to stream. Changing this value restarts the stream. */
  text: string;
  /** Optional mono-spaced prefix label rendered above the prose (e.g. "▸ RISK ANALYST") */
  agent?: string;
  /** Characters per second (default 70 ≈ fast-reading pace) */
  charsPerSec?: number;
  /** Fires once when the stream completes */
  onDone?: () => void;
  className?: string;
}

/**
 * Typewriter-streams `text` at ~70 chars/sec in Newsreader italic serif with
 * a blinking orange caret at the live edge. Fires `onDone` when finished.
 * Changing the `text` prop restarts the stream from scratch.
 */
export default function ReasoningStream({
  text,
  agent,
  charsPerSec = 70,
  onDone,
  className = "",
}: Props) {
  const [shown, setShown] = useState(0);
  const doneFiredRef = useRef(false);

  useEffect(() => {
    setShown(0);
    doneFiredRef.current = false;
    if (!text) return;
    const intervalMs = Math.max(5, Math.round(1000 / charsPerSec));
    const id = setInterval(() => {
      setShown((n) => {
        if (n >= text.length) {
          clearInterval(id);
          if (!doneFiredRef.current) {
            doneFiredRef.current = true;
            onDone?.();
          }
          return n;
        }
        return n + 1;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [text, charsPerSec, onDone]);

  const isDone = shown >= text.length;

  return (
    <div className={className}>
      {agent && (
        <div className="text-[10px] font-mono tracking-[0.14em] text-reasoner-mute mb-1.5">
          {agent}
        </div>
      )}
      <p className="font-serif italic text-[15px] leading-relaxed text-reasoner-body">
        {text.slice(0, shown)}
        {!isDone && (
          <span
            className="inline-block align-text-bottom ml-0.5 bg-reasoner-accent"
            style={{
              width: "2px",
              height: "14px",
              animation: "dotPulse 1s infinite",
            }}
          />
        )}
      </p>
    </div>
  );
}
