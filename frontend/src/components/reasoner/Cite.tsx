import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import ReactDOM from "react-dom";

export interface CiteSource {
  /** e.g. "orchestrator.compute_verdict". Renders in the popover header (mono) */
  source: string;
  /** Plain-English description of what this number represents */
  description: string;
  /** Optional raw value or formula. Rendered in a mono block beneath the description */
  value?: string;
  /** Optional footnote (e.g. "median × price × 52 × 0.8") */
  formula?: string;
}

interface Props {
  source: CiteSource;
  /** Citation index within the card. If omitted, a small "ⓘ" glyph is used instead of a number. */
  index?: number;
  children: ReactNode;
}

const POPOVER_WIDTH = 320;
const GAP = 8;

/**
 * Inline citation primitive. Wraps a cited piece of content with a subtle
 * dotted underline + superscript index; on hover (or focus/click), a popover
 * reveals the source, description, and optional raw value.
 *
 * The popover is rendered via React portal into document.body so it escapes
 * ancestor overflow constraints (ArtifactCard's overflow-hidden was clipping
 * popovers anchored in card headers). Position is recomputed on each open
 * with viewport-aware fallback (flip below if no room above).
 */
export default function Cite({ source, index, children }: Props) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; placement: "above" | "below" } | null>(null);
  const showT = useRef<number | null>(null);
  const hideT = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (showT.current) window.clearTimeout(showT.current);
      if (hideT.current) window.clearTimeout(hideT.current);
    };
  }, []);

  // Recalculate position once we know the popover's actual height.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const tr = triggerRef.current.getBoundingClientRect();
    const popH = popoverRef.current?.offsetHeight ?? 180;
    const roomAbove = tr.top;
    const roomBelow = window.innerHeight - tr.bottom;
    const placement: "above" | "below" =
      roomAbove >= popH + GAP || roomAbove >= roomBelow ? "above" : "below";
    const top =
      placement === "above"
        ? Math.max(8, tr.top - popH - GAP)
        : Math.min(window.innerHeight - popH - 8, tr.bottom + GAP);
    const left = Math.min(
      Math.max(8, tr.left),
      window.innerWidth - POPOVER_WIDTH - 8,
    );
    setPos({ top, left, placement });
  }, [open]);

  const schedule = (visible: boolean) => {
    if (showT.current) window.clearTimeout(showT.current);
    if (hideT.current) window.clearTimeout(hideT.current);
    const id = window.setTimeout(() => setOpen(visible), visible ? 300 : 200);
    if (visible) showT.current = id;
    else hideT.current = id;
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (showT.current) window.clearTimeout(showT.current);
    if (hideT.current) window.clearTimeout(hideT.current);
    setOpen((v) => !v);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      setOpen((v) => !v);
    }
    if (e.key === "Escape") setOpen(false);
  };

  return (
    <span
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={() => schedule(true)}
      onMouseLeave={() => schedule(false)}
    >
      <span
        role="button"
        tabIndex={0}
        onClick={handleClick}
        onKeyDown={handleKey}
        onFocus={() => schedule(true)}
        onBlur={() => schedule(false)}
        className="border-b border-dotted border-reasoner-dim cursor-help focus:outline-none focus:ring-1 focus:ring-reasoner-accent/40 rounded-[2px]"
      >
        {children}
      </span>
      <sup className="font-mono text-[9px] text-reasoner-accent font-semibold ml-0.5 select-none">
        {index ?? "ⓘ"}
      </sup>

      {open &&
        pos &&
        ReactDOM.createPortal(
          <div
            ref={popoverRef}
            className="fixed z-[60] p-3 rounded-lg bg-reasoner-ink text-reasoner-paper shadow-lg pointer-events-auto"
            style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
            onMouseEnter={() => schedule(true)}
            onMouseLeave={() => schedule(false)}
            role="tooltip"
          >
            <span className="block font-mono text-[10px] text-reasoner-accent-2 tracking-[0.08em] mb-1">
              {source.source}
            </span>
            <span className="block text-[12.5px] leading-relaxed text-reasoner-paper">
              {source.description}
            </span>
            {source.value && (
              <span className="block mt-2 pt-2 border-t border-reasoner-paper/15 font-mono text-[11px] tabular-nums text-reasoner-paper">
                {source.value}
              </span>
            )}
            {source.formula && (
              <span className="block mt-1 font-mono text-[10px] text-reasoner-paper/60 italic">
                {source.formula}
              </span>
            )}
          </div>,
          document.body,
        )}
    </span>
  );
}
