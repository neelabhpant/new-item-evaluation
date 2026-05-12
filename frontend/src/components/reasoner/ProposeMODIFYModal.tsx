import { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { buildEmailDraft, buildEmlFile, type EmailDraftInput } from "../../utils/emailDraft";

interface Props {
  open: boolean;
  onClose: () => void;
  draftInput: EmailDraftInput;
}

export default function ProposeMODIFYModal({ open, onClose, draftInput }: Props) {
  const initial = buildEmailDraft(draftInput);
  const [to, setTo] = useState(initial.to);
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState(initial.body);
  const [copied, setCopied] = useState(false);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  // Re-seed fields when the modal opens for a new submission
  useEffect(() => {
    if (!open) return;
    const fresh = buildEmailDraft(draftInput);
    setTo(fresh.to);
    setSubject(fresh.subject);
    setBody(fresh.body);
    setCopied(false);
    // Focus the close button briefly to trap the tab inside the modal
    window.setTimeout(() => closeBtnRef.current?.focus(), 50);
  }, [open, draftInput]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleCopy = async () => {
    const fullText = `Subject: ${subject}\nTo: ${to}\n\n${body}`;
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // fallback — leave copied=false
    }
  };

  const handleDownload = () => {
    const content = buildEmlFile({ to, from: initial.from, subject, body });
    const blob = new Blob([content], { type: "message/rfc822" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `propose-modify-${Date.now()}.eml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-0 bg-reasoner-ink/60 backdrop-blur-sm" />
      <div
        className="relative bg-reasoner-paper rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center gap-3 px-5 py-4 border-b border-reasoner-line">
          <span className="text-[10px] font-mono tracking-[0.12em] text-reasoner-accent">
            ↻ PROPOSE MODIFY
          </span>
          <h2 className="text-[15px] font-semibold text-reasoner-ink">
            {draftInput.productName}
          </h2>
          <span className="flex-1" />
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            className="w-8 h-8 grid place-items-center text-reasoner-mute hover:text-reasoner-ink hover:bg-reasoner-bg rounded-md transition-colors"
            aria-label="Close"
          >
            <span className="text-xl leading-none">×</span>
          </button>
        </header>

        <div className="px-5 py-4 overflow-auto space-y-3">
          <div>
            <label className="block text-[10px] font-mono tracking-[0.12em] text-reasoner-mute mb-1">
              TO
            </label>
            <input
              type="text"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="w-full border border-reasoner-line rounded-md px-3 py-2 text-sm font-mono text-reasoner-ink focus:outline-none focus:border-reasoner-accent focus:ring-2 focus:ring-reasoner-accent/20"
            />
          </div>
          <div>
            <label className="block text-[10px] font-mono tracking-[0.12em] text-reasoner-mute mb-1">
              SUBJECT
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full border border-reasoner-line rounded-md px-3 py-2 text-sm text-reasoner-ink focus:outline-none focus:border-reasoner-accent focus:ring-2 focus:ring-reasoner-accent/20"
            />
          </div>
          <div>
            <label className="block text-[10px] font-mono tracking-[0.12em] text-reasoner-mute mb-1">
              MESSAGE
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={18}
              className="w-full border border-reasoner-line rounded-md px-3 py-2 text-sm font-serif text-reasoner-body leading-relaxed resize-y focus:outline-none focus:border-reasoner-accent focus:ring-2 focus:ring-reasoner-accent/20"
            />
          </div>
        </div>

        <footer className="flex items-center gap-3 px-5 py-3 border-t border-reasoner-line bg-reasoner-bg">
          <span className="text-[11px] font-mono text-reasoner-mute italic">
            Draft stays local. No SMTP, no CRM. Copy or download to send via your mail client.
          </span>
          <span className="flex-1" />
          <button
            type="button"
            onClick={handleCopy}
            className="px-3.5 py-1.5 text-[13px] font-semibold text-reasoner-ink bg-reasoner-paper border border-reasoner-line rounded-md hover:bg-reasoner-bg transition-colors"
          >
            {copied ? "Copied ✓" : "Copy to clipboard"}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="px-3.5 py-1.5 text-[13px] font-semibold text-reasoner-ink bg-reasoner-paper border border-reasoner-line rounded-md hover:bg-reasoner-bg transition-colors"
          >
            Download .eml
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 text-[13px] font-semibold text-reasoner-paper bg-reasoner-accent rounded-md hover:bg-reasoner-accent-2 transition-colors"
          >
            Close
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
