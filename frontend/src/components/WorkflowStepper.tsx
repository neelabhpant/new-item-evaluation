import type { StepState } from "../types";

function StepIcon({ status }: { status: StepState["status"] }) {
  if (status === "complete") {
    return (
      <div className="w-10 h-10 rounded-full bg-green-brand flex items-center justify-center">
        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }
  if (status === "running") {
    return (
      <div className="w-10 h-10 rounded-full bg-orange-brand flex items-center justify-center">
        <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="w-10 h-10 rounded-full bg-red-brand flex items-center justify-center">
        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    );
  }
  return (
    <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
      <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </div>
  );
}

function statusLabel(step: StepState): string {
  if (step.status === "complete" && step.message) {
    return step.message.length > 30 ? step.message.slice(0, 30) + "..." : step.message;
  }
  if (step.status === "running") return "Currently Running";
  if (step.status === "error") return "Error";
  return "Pending";
}

function statusColor(status: StepState["status"]): string {
  if (status === "complete") return "text-green-brand";
  if (status === "running") return "text-orange-brand";
  if (status === "error") return "text-red-brand";
  return "text-gray-400";
}

interface Props {
  steps: StepState[];
}

export default function WorkflowStepper({ steps }: Props) {
  return (
    <div className="bg-white border-b border-gray-border px-6 py-5">
      <div className="flex items-start justify-between max-w-5xl mx-auto">
        {steps.map((step, i) => (
          <div key={step.step} className="flex items-start">
            <div className="flex flex-col items-center gap-1.5 min-w-[120px]">
              <StepIcon status={step.status} />
              <span
                className={`text-xs font-semibold text-center leading-tight ${
                  step.status === "running" ? "text-orange-brand" : "text-gray-900"
                }`}
              >
                {step.stepName}
              </span>
              <span className={`text-[10px] text-center leading-tight ${statusColor(step.status)}`}>
                {statusLabel(step)}
              </span>
              {step.status === "running" && (
                <div className="w-16 h-1 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-full bg-orange-brand rounded-full animate-pulse w-2/3" />
                </div>
              )}
            </div>
            {i < steps.length - 1 && (
              <div
                className={`w-12 h-0.5 mt-5 mx-1 ${
                  step.status === "complete" ? "bg-green-brand" : "bg-gray-200"
                }`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
