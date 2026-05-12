import { useCallback, useRef, useState } from "react";

export type FollowupStatus = "idle" | "running" | "complete" | "error";

interface FollowupMessage {
  status: "running" | "complete" | "error";
  chunk?: string;
  output?: string;
  message?: string;
}

export function useFollowupSocket() {
  const [text, setText] = useState("");
  const [status, setStatus] = useState<FollowupStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const ask = useCallback(
    async (evaluationId: string, question: string) => {
      setText("");
      setStatus("running");
      setErrorMessage(null);

      let followupId: string;
      try {
        const resp = await fetch(`/api/evaluate/followup/${evaluationId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          setStatus("error");
          setErrorMessage(err?.error ?? `Follow-up request failed (HTTP ${resp.status})`);
          return;
        }
        const data = await resp.json();
        followupId = data.followup_id;
      } catch (e) {
        setStatus("error");
        setErrorMessage(`Follow-up request failed: ${(e as Error).message}`);
        return;
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(
        `${protocol}//${window.location.host}/ws/followup/${followupId}`,
      );
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg: FollowupMessage = JSON.parse(event.data);
        if (msg.status === "running" && msg.chunk) {
          setText((prev) => prev + msg.chunk);
        } else if (msg.status === "complete") {
          if (msg.output) setText(msg.output);
          setStatus("complete");
        } else if (msg.status === "error") {
          setStatus("error");
          setErrorMessage(msg.message ?? "Follow-up failed");
        }
      };

      ws.onerror = () => {
        setStatus("error");
        setErrorMessage("WebSocket error during follow-up");
      };
      ws.onclose = () => {
        wsRef.current = null;
      };
    },
    [],
  );

  return { text, status, errorMessage, ask };
}
