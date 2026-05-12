import { useEffect, useState } from "react";
import type { StepState } from "../../types";
import Cite from "./Cite";
import VerdictActions from "./VerdictActions";

interface Props {
  step: StepState | undefined;
  finalOutput: string | null;
  isDone: boolean;
  productName?: string;
  brand?: string;
}

type Verdict = "AUTHORIZE" | "DECLINE" | "MODIFY" | "";

function strip(text: string): string {
  return text.replace(/\*\*/g, "");
}

function extractVerdict(output: string): Verdict {
  const labeled = output.match(/VERDICT:\s*(AUTHORIZE|DECLINE|MODIFY)/i);
  if (labeled) return labeled[1].toUpperCase() as Verdict;
  if (/\bAUTHORIZE\b/i.test(output)) return "AUTHORIZE";
  if (/\bDECLINE\b/i.test(output)) return "DECLINE";
  if (/\bMODIFY\b/i.test(output)) return "MODIFY";
  return "";
}

function extractConfidence(output: string): number {
  const labeled = output.match(/CONFIDENCE:\s*(\d+)%?/i);
  if (labeled) return parseInt(labeled[1], 10);
  const match = output.match(/(?:confidence)[:\s]*(\d+)%?/i);
  return match ? parseInt(match[1], 10) : 0;
}

function extractReasons(output: string): string[] {
  const reasons: string[] = [];
  const r1 = output.match(/REASON_1:\s*([^\n]+)/i);
  const r2 = output.match(/REASON_2:\s*([^\n]+)/i);
  const r3 = output.match(/REASON_3:\s*([^\n]+)/i);
  if (r1) reasons.push(strip(r1[1].trim()));
  if (r2) reasons.push(strip(r2[1].trim()));
  if (r3) reasons.push(strip(r3[1].trim()));
  return reasons;
}

function extractActionLine(output: string): string {
  const retail = output.match(/SUGGESTED_RETAIL:\s*([^\n]+)/i);
  const placement = output.match(/PLACEMENT:\s*([^\n]+)/i);
  const rollout = output.match(/ROLLOUT:\s*([^\n]+)/i);
  const parts: string[] = [];
  if (retail) {
    const v = strip(retail[1].trim());
    if (v && !/^N\/A$/i.test(v)) parts.push(`Suggested retail: ${v}`);
  }
  if (placement) {
    const v = strip(placement[1].trim());
    if (v && !/^N\/A$/i.test(v)) parts.push(`Placement: ${v}`);
  }
  if (rollout) {
    const v = strip(rollout[1].trim());
    if (v && !/^0 stores$/i.test(v) && !/^N\/A$/i.test(v)) parts.push(`Rollout: ${v}`);
  }
  return parts.join("  ·  ");
}

function extractReplaceSkus(output: string): string {
  const m = output.match(/REPLACE_SKUS:\s*([^\n]+)/i);
  if (!m) return "";
  const val = strip(m[1].trim());
  if (/^NONE$/i.test(val)) return "";
  return val;
}

function extractReplacementNetImpact(output: string): string {
  const m = output.match(/REPLACEMENT_NET_IMPACT:\s*([^\n]+)/i);
  if (!m) return "";
  const val = strip(m[1].trim());
  if (/^N\/A$/i.test(val)) return "";
  return val;
}

function verdictColorClass(verdict: Verdict): string {
  if (verdict === "AUTHORIZE") return "text-reasoner-green";
  if (verdict === "DECLINE") return "text-reasoner-red";
  if (verdict === "MODIFY") return "text-amber-700";
  return "text-reasoner-ink";
}

/**
 * Animated integer counter — 0 → target with ease-out cubic.
 */
function useCountUp(target: number, durationMs = 900): number {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (target <= 0) {
      setShown(0);
      return;
    }
    const start = Date.now();
    const id = setInterval(() => {
      const t = Math.min(1, (Date.now() - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(Math.round(target * eased));
      if (t >= 1) clearInterval(id);
    }, 16);
    return () => clearInterval(id);
  }, [target, durationMs]);
  return shown;
}

export default function VerdictHero({ step, finalOutput, isDone, productName, brand }: Props) {
  const rawOutput = finalOutput ?? step?.output ?? null;
  const output = rawOutput ? strip(rawOutput) : null;

  const verdict: Verdict = output ? extractVerdict(output) : "";
  const confidence = output ? extractConfidence(output) : 0;
  const reasons = output ? extractReasons(output) : [];
  const actionLine = output ? extractActionLine(output) : "";
  const replaceSkus = output ? extractReplaceSkus(output) : "";
  const replacementNetImpact = output ? extractReplacementNetImpact(output) : "";

  const shown = useCountUp(confidence);

  // Pending state before any verdict arrives
  if (!isDone && (!step || step.status === "pending" || !verdict)) {
    return (
      <section id="verdict-artifact" className="rounded-[10px] bg-reasoner-paper border border-reasoner-line p-8">
        <div className="text-[10px] font-mono tracking-[0.14em] text-reasoner-mute mb-3">
          VERDICT · PENDING
        </div>
        <div className="animate-pulse space-y-3">
          <div className="h-16 bg-reasoner-line/50 rounded w-1/3" />
          <div className="h-4 bg-reasoner-line/50 rounded w-2/3" />
          <div className="h-4 bg-reasoner-line/50 rounded w-1/2" />
        </div>
      </section>
    );
  }

  const showPathToModify = verdict === "DECLINE" && replacementNetImpact;

  return (
    <section id="verdict-artifact" className="rounded-[10px] bg-reasoner-paper border border-reasoner-line p-8">
      <div className="text-[10px] font-mono tracking-[0.14em] text-reasoner-mute mb-5">
        VERDICT · FINAL
      </div>

      <div className="flex items-end gap-10 flex-wrap">
        <Cite
          index={1}
          source={{
            source: "orchestrator.compute_verdict()",
            description:
              "Deterministic verdict from the decision matrix: overlap classification (similarity tier) × category saturation (SKU count).",
            value: `verdict = ${verdict}`,
            formula: "High Overlap + Full category ⇒ DECLINE · Moderate + Has room ⇒ AUTHORIZE · etc.",
          }}
        >
          <h1
            className={`font-sans font-bold tracking-tighter leading-none ${verdictColorClass(verdict)}`}
            style={{ fontSize: "72px" }}
          >
            {verdict}.
          </h1>
        </Cite>

        {confidence > 0 && (
          <div className="pb-2">
            <div className="text-[10px] font-mono tracking-[0.14em] text-reasoner-mute">
              CONFIDENCE
            </div>
            <div className="text-[48px] font-semibold tabular-nums text-reasoner-ink leading-none mt-1">
              <Cite
                index={2}
                source={{
                  source: "orchestrator.compute_verdict()",
                  description:
                    "Confidence is keyed to the decision-matrix bucket this evaluation fell into. Not an LLM score. A deterministic number derived from overlap + saturation.",
                  value: `${confidence}%`,
                }}
              >
                <span>{shown}</span>
                <span className="text-reasoner-dim">%</span>
              </Cite>
            </div>
          </div>
        )}
      </div>

      {/* Amber rule sweep */}
      <div
        className="mt-6 h-px bg-reasoner-accent origin-left"
        style={{ animation: "ruleSweep 600ms 200ms ease-out both" }}
      />

      {reasons.length > 0 && (
        <ol className="mt-6 space-y-4">
          {reasons.map((r, i) => (
            <li key={i} className="grid grid-cols-[40px_1fr] gap-3 items-baseline">
              <span className="font-serif italic text-[32px] font-medium text-reasoner-accent tabular-nums leading-none">
                {String(i + 1).padStart(2, "0")}
              </span>
              <p className="font-serif italic text-[15px] leading-relaxed text-reasoner-body">
                {r}
              </p>
            </li>
          ))}
        </ol>
      )}

      {showPathToModify && (
        <p className="mt-6 pt-4 border-t border-reasoner-line font-serif italic text-[14px] text-reasoner-mute leading-relaxed">
          <span className="not-italic font-sans font-semibold text-reasoner-accent">
            with a path to MODIFY
          </span>{" "}
          : {replacementNetImpact.toLowerCase()}.
        </p>
      )}

      {!showPathToModify && actionLine && (
        <p className="mt-6 pt-4 border-t border-reasoner-line font-mono text-[11px] tracking-[0.06em] text-reasoner-mute">
          {actionLine}
        </p>
      )}

      {verdict !== "DECLINE" && replaceSkus && (
        <div className="mt-4 bg-amber-50/60 border border-amber-200 rounded-lg p-3">
          <div className="text-[10px] font-mono font-semibold text-amber-800 mb-1 tracking-[0.1em]">
            ACTION ITEMS
          </div>
          <div className="text-xs text-reasoner-body">
            <span className="font-semibold text-reasoner-ink">Deauthorize:</span> {replaceSkus}
          </div>
          {replacementNetImpact && (
            <div className="text-xs text-reasoner-body mt-1">
              <span className="font-semibold text-reasoner-ink">Net category improvement:</span>{" "}
              <span className="font-mono tabular-nums">{replacementNetImpact}</span>
            </div>
          )}
        </div>
      )}

      <VerdictActions
        verdict={verdict}
        productName={productName}
        brand={brand}
        confidence={confidence}
        reasons={reasons}
        replaceSkus={replaceSkus}
        replacementNetImpact={replacementNetImpact}
      />
    </section>
  );
}
