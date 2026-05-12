import { useCallback, useRef, useState } from "react";
import type { EvaluationMessage, StepState } from "../types";

const STEP_NAMES = [
  "Submission Processed",
  "Visual Similarity",
  "Data Collection",
  "Risk & Market Analysis",
  "Financial Projection",
  "Recommendation",
];

function initialSteps(): StepState[] {
  return STEP_NAMES.map((name, i) => ({
    step: i + 1,
    stepName: name,
    status: "pending",
    message: "",
    output: null,
  }));
}

export function useEvaluationSocket() {
  const [steps, setSteps] = useState<StepState[]>(initialSteps());
  const [isRunning, setIsRunning] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [finalOutput, setFinalOutput] = useState<string | null>(null);
  const [evaluationId, setEvaluationId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback((evaluationId: string) => {
    setEvaluationId(evaluationId);
    setSteps(initialSteps());
    setIsRunning(true);
    setIsDone(false);
    setFinalOutput(null);

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//${window.location.host}/ws/evaluation/${evaluationId}`
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg: EvaluationMessage = JSON.parse(event.data);

      if (msg.status === "error") {
        setSteps((prev) =>
          prev.map((s) =>
            s.step === msg.step ? { ...s, status: "error", message: msg.message } : s
          )
        );
        setIsRunning(false);
        return;
      }

      if (msg.status === "done") {
        setFinalOutput(msg.output);
        setIsRunning(false);
        setIsDone(true);
        return;
      }

      setSteps((prev) =>
        prev.map((s) => {
          if (s.step === msg.step) {
            const nextStatus = msg.status === "complete" ? "complete" : "running";
            const now = Date.now();
            return {
              ...s,
              status: nextStatus,
              message: msg.message,
              output: msg.output ?? s.output,
              reasoning: msg.reasoning ?? s.reasoning,
              startedAt: s.startedAt ?? (nextStatus === "running" ? now : undefined),
              completedAt: nextStatus === "complete" ? now : s.completedAt,
            };
          }
          return s;
        })
      );
    };

    ws.onerror = () => {
      setIsRunning(false);
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, []);

  const reset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setSteps(initialSteps());
    setIsRunning(false);
    setIsDone(false);
    setFinalOutput(null);
  }, []);

  /**
   * Instant-hydrate the evaluation state from a cached backend result payload.
   * Used by the Last Session Replay flow — no WebSocket, no typewriter re-run.
   */
  const restoreFromResult = useCallback(
    (payload: {
      evaluation_id: string;
      data_package: any; // eslint-disable-line @typescript-eslint/no-explicit-any
      tasks_output: string[];
      reasonings: string[];
      final_output: string;
    }) => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setEvaluationId(payload.evaluation_id);

      const dp = payload.data_package || {};
      const similarOutput = JSON.stringify({
        similar_products: dp.similar_products ?? [],
        enriched_products: dp.enriched_products ?? [],
        classification: dp.overlap_classification ?? "",
        category_groups: dp.category_groups ?? [],
        inferred_category: dp.inferred_category ?? "",
      });

      const now = Date.now();
      const makeStep = (
        step: number,
        stepName: string,
        output: string | null,
        reasoning?: string,
      ): StepState => ({
        step,
        stepName,
        status: "complete",
        message: "",
        output,
        reasoning,
        startedAt: now,
        completedAt: now,
      });

      setSteps([
        makeStep(1, STEP_NAMES[0], null),
        makeStep(2, STEP_NAMES[1], similarOutput),
        makeStep(3, STEP_NAMES[2], null),
        makeStep(4, STEP_NAMES[3], payload.tasks_output[0] ?? "", payload.reasonings[0]),
        makeStep(5, STEP_NAMES[4], payload.tasks_output[1] ?? "", payload.reasonings[1]),
        makeStep(6, STEP_NAMES[5], payload.tasks_output[2] ?? "", payload.reasonings[2]),
      ]);
      setIsRunning(false);
      setIsDone(true);
      setFinalOutput(payload.final_output || null);
    },
    [],
  );

  return { steps, isRunning, isDone, finalOutput, evaluationId, connect, reset, restoreFromResult };
}

/**
 * Returns a human-readable elapsed label for a step, e.g. "2.1s".
 * - Running step: time since it started
 * - Completed step: total duration
 * - Pending/undefined: empty string
 */
export function elapsedLabel(step: StepState | undefined, nowMs?: number): string {
  if (!step || !step.startedAt) return "";
  const end = step.completedAt ?? nowMs ?? Date.now();
  const seconds = Math.max(0, (end - step.startedAt) / 1000);
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return `${Math.round(seconds)}s`;
}
