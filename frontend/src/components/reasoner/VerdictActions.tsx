import { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import { useWatchlist } from "../../hooks/useWatchlist";
import ProposeMODIFYModal from "./ProposeMODIFYModal";
import type { EmailDraftInput } from "../../utils/emailDraft";

type Verdict = "AUTHORIZE" | "DECLINE" | "MODIFY" | "";

interface Props {
  verdict: Verdict;
  productName?: string;
  brand?: string;
  confidence: number;
  reasons: string[];
  replaceSkus: string;
  replacementNetImpact: string;
}

function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const id = window.setTimeout(onDone, 2400);
    return () => window.clearTimeout(id);
  }, [onDone]);
  return ReactDOM.createPortal(
    <div className="fixed bottom-6 right-6 z-[60] max-w-sm bg-reasoner-ink text-reasoner-paper px-4 py-3 rounded-lg shadow-lg text-[13px]">
      {message}
    </div>,
    document.body,
  );
}

export default function VerdictActions({
  verdict,
  productName,
  brand,
  confidence,
  reasons,
  replaceSkus,
  replacementNetImpact,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { isOn: onWatchlist, toggle: toggleWatchlist } = useWatchlist(productName);

  if (!verdict || !productName) return null;

  const primaryLabel =
    verdict === "DECLINE"
      ? "↻ Propose MODIFY to supplier"
      : verdict === "MODIFY"
        ? "↻ Send revision requests"
        : "Proceed to planogram approval";

  const canPropose = verdict === "DECLINE" || verdict === "MODIFY";

  const handlePrimary = () => {
    if (canPropose) {
      setModalOpen(true);
    } else {
      setToast("Coming soon. Planogram approval workflow is next.");
    }
  };

  const handleCompare = () => {
    setToast("Coming soon. This will surface the 3 closest near-competitors to compare.");
  };

  const draftInput: EmailDraftInput = {
    productName,
    brand,
    verdict,
    confidence,
    reasons,
    replaceSkus,
    replacementNetImpact,
  };

  return (
    <div className="mt-6 pt-5 border-t border-reasoner-line">
      <div className="flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onClick={handlePrimary}
          className="px-4 py-2 text-[13px] font-semibold text-reasoner-paper bg-reasoner-accent rounded-md hover:bg-reasoner-accent-2 transition-colors"
        >
          {primaryLabel}
        </button>
        <button
          type="button"
          onClick={() => toggleWatchlist(verdict)}
          className={`px-4 py-2 text-[13px] font-semibold rounded-md border transition-colors ${
            onWatchlist
              ? "bg-reasoner-green/10 border-reasoner-green/30 text-reasoner-green"
              : "bg-reasoner-paper border-reasoner-line text-reasoner-ink hover:bg-reasoner-bg"
          }`}
        >
          {onWatchlist ? "Added to watchlist ✓" : "Add to watchlist"}
        </button>
        <button
          type="button"
          onClick={handleCompare}
          className="px-4 py-2 text-[13px] font-semibold text-reasoner-ink bg-reasoner-paper border border-reasoner-line rounded-md hover:bg-reasoner-bg transition-colors"
        >
          Compare to alternatives
        </button>
      </div>

      <ProposeMODIFYModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        draftInput={draftInput}
      />

      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  );
}
