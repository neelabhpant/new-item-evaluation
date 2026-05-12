export interface EmailDraftInput {
  productName: string;
  brand?: string;
  verdict: string;
  confidence?: number;
  reasons: string[];
  replaceSkus?: string;
  replacementNetImpact?: string;
}

export interface EmailDraft {
  to: string;
  from: string;
  subject: string;
  body: string;
}

function brandToDomain(brand?: string): string {
  if (!brand) return "supplier.example";
  return brand
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "")
    .replace(/^$/, "supplier");
}

export function buildEmailDraft(input: EmailDraftInput): EmailDraft {
  const {
    productName,
    brand,
    verdict,
    reasons,
    replaceSkus,
    replacementNetImpact,
  } = input;

  const to = `sales@${brandToDomain(brand)}.com`;
  const from = "merchandising@retailer.example";
  const supplier = brand || "team";

  const nReplacements = replaceSkus && !/^NONE$/i.test(replaceSkus)
    ? replaceSkus.split(",").length
    : 0;

  const subject =
    verdict === "DECLINE" && nReplacements > 0
      ? `RE: ${productName}: MODIFY pathway with ${nReplacements} replacements`
      : verdict === "MODIFY"
        ? `RE: ${productName}: revision requests before authorization`
        : verdict === "AUTHORIZE"
          ? `RE: ${productName}: authorized for shelf placement`
          : `RE: ${productName}: evaluation outcome`;

  const headline =
    verdict === "DECLINE" && nReplacements > 0
      ? "our decision is DECLINE with a viable path to MODIFY"
      : verdict === "DECLINE"
        ? "our decision is DECLINE"
        : verdict === "MODIFY"
          ? "our decision is MODIFY pending revisions"
          : "our decision is AUTHORIZE";

  const reasonBlock = reasons
    .filter(Boolean)
    .slice(0, 3)
    .map((r, i) => `  ${i + 1}. ${r}`)
    .join("\n");

  const replacementBlock =
    replaceSkus && !/^NONE$/i.test(replaceSkus)
      ? `Proposed path forward: replace these existing SKUs:
  ${replaceSkus}
Projected net category improvement: ${replacementNetImpact || "TBD"}.

`
      : "";

  const askBlock =
    verdict === "DECLINE" || verdict === "MODIFY"
      ? `Before we can authorize, please confirm:
  - Willingness to adjust pricing and/or positioning per the drivers above
  - Availability to replace the SKUs listed (if applicable)
  - Updated packaging claims that differentiate from the competitive set

`
      : `Next steps:
  - Confirm delivery schedule and initial rollout store count
  - Send finalized planogram-ready assets
  - Review fill-rate and OTIF expectations per our vendor scorecard

`;

  const closer =
    verdict === "AUTHORIZE"
      ? "We'll coordinate rollout timing within 10 business days.\n\nThank you,\nMerchandising Team"
      : "Please reply with your revised proposal. We'll re-evaluate and communicate next steps within 5 business days.\n\nThank you,\nMerchandising Team";

  const body = `Hello ${supplier},

Thank you for submitting ${productName} for evaluation. After review, ${headline}. Here is what drove the call:

${reasonBlock}

${replacementBlock}${askBlock}${closer}`;

  return { to, from, subject, body };
}

export function buildEmlFile(draft: EmailDraft): string {
  return [
    `From: ${draft.from}`,
    `To: ${draft.to}`,
    `Subject: ${draft.subject}`,
    `MIME-Version: 1.0`,
    `Content-Type: text/plain; charset=utf-8`,
    ``,
    draft.body,
  ].join("\r\n");
}
