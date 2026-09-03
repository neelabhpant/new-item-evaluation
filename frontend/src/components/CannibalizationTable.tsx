interface CannibalizationRow {
  sku: string;
  name: string;
  similarity: string;
  revenue: string;
  trend: string;
  risk: string;
  impact: string;
}

interface ReplacementCandidate {
  sku: string;
  name: string;
  revenue: string;
  reason: string;
}

interface VendorRisk {
  vendor: string;
  tier: string;
  detail: string;
}

// A SKU is trusted only when it looks like a barcode; any other leading token (e.g. the
// word "PRODUCT" copied from the prompt, or "") must never be used to match rows.
function isBarcode(sku: string): boolean {
  return /^\d{6,}$/.test(sku);
}

// Drop artefacts a model may leave in front of a product name ("1:", "PRODUCT 2:", "#3").
function cleanName(name: string): string {
  return name.replace(/^\s*(?:product\s*)?#?\d{1,3}\s*[:.)-]\s*/i, "").replace(/\*\*/g, "").trim();
}

function normalizeName(name: string): string {
  return cleanName(name).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function bulletLines(sectionText: string): string[] {
  return sectionText
    .split("\n")
    .map((l) => l.replace(/\*\*/g, "").trim())
    .filter((l) => l.startsWith("-"));
}

function parseCannibalizationDetails(text: string): CannibalizationRow[] {
  const rows: CannibalizationRow[] = [];
  const section = text.match(/CANNIBALIZATION_DETAILS:\s*\n([\s\S]*?)(?=\n[A-Z_]+:|$)/);
  if (!section) return rows;
  const lines = bulletLines(section[1]);
  for (const line of lines) {
    const m = line.match(
      /^-\s*(\S+)\s+(.+?):\s*(\d+)%\s*similar,\s*\$([\d,.]+[KMB]?)\/yr,\s*([\w\s+\-.%]+?),?\s*(\w+)\s*risk,?\s*est\.?\s*\$([\d,.]+[KMB]?)/i
    );
    if (m) {
      rows.push({
        sku: isBarcode(m[1]) ? m[1] : "",
        name: cleanName(isBarcode(m[1]) ? m[2] : `${m[1]} ${m[2]}`),
        similarity: m[3] + "%",
        revenue: "$" + m[4] + "/yr",
        trend: m[5].trim(),
        risk: m[6],
        impact: "$" + m[7],
      });
    } else {
      const nameM = line.match(/^-\s*(?:(\S+)\s+)?(.+?):\s*\d+%/);
      const simM = line.match(/(\d+)%\s*similar/i);
      const revM = line.match(/\$([\d,]+(?:\.\d+)?[KMB]?)\/yr/i);
      const trendM = line.match(/(growing|declining|stable)/i);
      const riskM = line.match(/(high|medium|low)\s*risk/i);
      const impactM = line.match(/est\.?\s*\$([\d,]+(?:\.\d+)?[KMB]?)/i);
      if (simM || revM) {
        const rawSku = nameM?.[1] ?? "";
        const rawName = nameM?.[2]?.trim() ?? line.replace(/^-\s*/, "").split(":")[0].trim();
        rows.push({
          sku: isBarcode(rawSku) ? rawSku : "",
          name: cleanName(isBarcode(rawSku) || !rawSku ? rawName : `${rawSku} ${rawName}`),
          similarity: simM ? simM[1] + "%" : "",
          revenue: revM ? "$" + revM[1] + "/yr" : "",
          trend: trendM ? trendM[1] : "",
          risk: riskM ? riskM[1] : "",
          impact: impactM ? "$" + impactM[1] : "",
        });
      }
    }
  }
  return rows;
}

function parseReplacementCandidates(text: string): ReplacementCandidate[] {
  const candidates: ReplacementCandidate[] = [];
  const section = text.match(/REPLACEMENT_CANDIDATES:\s*\n([\s\S]*?)(?=\n[A-Z_]+:|$)/);
  if (!section) return candidates;
  const lines = bulletLines(section[1]);
  for (const line of lines) {
    if (/^-\s*NONE\b/i.test(line)) continue;
    const m = line.match(/REPLACE\s+(\S+)\s+(.+?)\s*\(\$([\d,.]+[KMB]?)\/yr,?\s*(\w+)\)\s*--?\s*Reason:\s*(.*)/i);
    if (m) {
      const sku = isBarcode(m[1]) ? m[1] : "";
      candidates.push({ sku, name: cleanName(sku ? m[2] : `${m[1]} ${m[2]}`), revenue: "$" + m[3] + "/yr", reason: m[5].trim() });
    } else {
      const cleaned = line.replace(/^-\s*(REPLACE\s+)?/i, "").trim();
      if (cleaned) {
        const skuM = cleaned.match(/^(\d{6,})\s+/);
        const namePart = cleaned.replace(/^(\d{6,})\s+/, "").split("(")[0].split(" -- ")[0];
        candidates.push({ sku: skuM ? skuM[1] : "", name: cleanName(namePart), revenue: "", reason: cleaned });
      }
    }
  }
  return candidates;
}

function parseReplacementScenario(text: string): { decline: string; newRevenue: string; net: string } | null {
  const decline = text.match(/REPLACEMENT_PROJECTED_DECLINE:\s*\$([\d,.]+[KMB]?)/i)
    ?? text.match(/REPLACEMENT_SCENARIO_REVENUE_LOST:\s*\$([\d,.]+[KMB]?)/i);
  const newRev = text.match(/REPLACEMENT_NEW_PRODUCT_REVENUE:\s*\$([\d,.]+[KMB]?)/i)
    ?? text.match(/REPLACEMENT_SCENARIO_REVENUE_GAINED:\s*\$([\d,.]+[KMB]?)/i);
  const net = text.match(/REPLACEMENT_NET_INCREMENTAL:\s*(.*)/i)
    ?? text.match(/REPLACEMENT_SCENARIO_NET:\s*(.*)/i);
  if (!net) return null;
  return {
    decline: decline ? "$" + decline[1] : "$0",
    newRevenue: newRev ? "$" + newRev[1] : "$0",
    net: net[1].trim(),
  };
}

function parseVendorRisks(text: string): VendorRisk[] {
  const risks: VendorRisk[] = [];
  const section = text.match(/VENDOR_RISKS:\s*\n([\s\S]*?)(?=\n[A-Z_]+:|$)/);
  if (!section) return risks;
  const lines = bulletLines(section[1]);
  for (const line of lines) {
    if (/^-\s*NONE\b/i.test(line)) continue;
    const m = line.match(/^-\s*(.+?)\s*\((\w+)\):\s*(.*)/);
    if (m) {
      risks.push({ vendor: m[1].trim(), tier: m[2].trim(), detail: m[3].trim() });
    }
  }
  return risks;
}

function riskColor(risk: string): string {
  const r = risk.toUpperCase();
  if (r.includes("HIGH")) return "bg-red-50 text-reasoner-red";
  if (r.includes("MEDIUM")) return "bg-amber-50 text-amber-700";
  return "bg-emerald-50 text-reasoner-green";
}

function trendColor(trend: string): string {
  const t = trend.toLowerCase();
  if (t.includes("growing")) return "text-reasoner-green";
  if (t.includes("declining")) return "text-reasoner-red";
  return "text-reasoner-mute";
}

function tierBadgeColor(tier: string): string {
  if (tier === "Strategic") return "bg-reasoner-cyan/15 text-reasoner-cyan";
  if (tier === "Preferred") return "bg-reasoner-green/15 text-reasoner-green";
  if (tier === "Probationary") return "bg-red-50 text-reasoner-red";
  return "bg-reasoner-line/50 text-reasoner-mute";
}

interface Props {
  output: string;
}

export default function CannibalizationTable({ output }: Props) {
  const rows = parseCannibalizationDetails(output);
  const replacements = parseReplacementCandidates(output);
  const scenario = parseReplacementScenario(output);
  const vendorRisks = parseVendorRisks(output);

  if (rows.length === 0 && replacements.length === 0) return null;

  // Match rows to replacement candidates by barcode when both sides have one, otherwise by
  // normalized product name. An empty or non-barcode token can never mark a row.
  const replacementSkus = new Set(replacements.map((r) => r.sku).filter(isBarcode));
  const replacementNames = new Set(replacements.map((r) => normalizeName(r.name)).filter((n) => n.length > 2));
  const isReplacementRow = (row: CannibalizationRow): boolean => {
    if (row.sku && replacementSkus.has(row.sku)) return true;
    if (row.sku && replacementSkus.size > 0) return false;
    return replacementNames.has(normalizeName(row.name));
  };

  return (
    <div className="space-y-4">
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-reasoner-line">
                <th className="text-left py-1.5 pr-2 font-semibold text-reasoner-body">Product</th>
                <th className="text-right py-1.5 px-2 font-semibold text-reasoner-body">Similarity</th>
                <th className="text-right py-1.5 px-2 font-semibold text-reasoner-body">Revenue</th>
                <th className="text-center py-1.5 px-2 font-semibold text-reasoner-body">Trend</th>
                <th className="text-center py-1.5 px-2 font-semibold text-reasoner-body">Risk</th>
                <th className="text-right py-1.5 pl-2 font-semibold text-reasoner-body">Est. Impact</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const isReplacement = isReplacementRow(row);
                return (
                  <tr key={i} className={`border-b border-reasoner-line/60 ${isReplacement ? "bg-amber-50/60" : ""}`}>
                    <td className="py-1.5 pr-2">
                      <span className="font-medium text-reasoner-ink">{row.name}</span>
                      {isReplacement && (
                        <span className="ml-1 text-[9px] font-mono font-bold bg-amber-200 text-amber-800 px-1 py-0.5 rounded tracking-[0.05em]">
                          REPLACE
                        </span>
                      )}
                      {row.sku && <span className="block text-[10px] font-mono text-reasoner-dim">{row.sku}</span>}
                    </td>
                    <td className="text-right py-1.5 px-2 font-mono tabular-nums text-reasoner-body">{row.similarity}</td>
                    <td className="text-right py-1.5 px-2 font-mono tabular-nums text-reasoner-body">{row.revenue}</td>
                    <td className={`text-center py-1.5 px-2 ${trendColor(row.trend)}`}>{row.trend}</td>
                    <td className="text-center py-1.5 px-2">
                      <span className={`inline-block text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded tracking-[0.05em] ${riskColor(row.risk)}`}>
                        {row.risk.toUpperCase()}
                      </span>
                    </td>
                    <td className="text-right py-1.5 pl-2 font-mono tabular-nums text-reasoner-red">-{row.impact}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(replacements.length > 0 || scenario) && (
        <div className="bg-amber-50/60 border border-amber-200 rounded-lg p-3">
          <h4 className="text-[10px] font-mono font-semibold text-amber-800 mb-2 tracking-[0.1em]">REPLACEMENT SCENARIO</h4>
          {replacements.length > 0 && (
            <div className="space-y-1 mb-2">
              {replacements.map((r, i) => (
                <div key={i} className="text-xs">
                  <span className="font-medium text-reasoner-ink">Replace {r.name || r.sku}</span>
                  {r.revenue && <span className="text-reasoner-mute font-mono tabular-nums"> ({r.revenue})</span>}
                  {r.reason && <span className="text-reasoner-body"> · {r.reason}</span>}
                </div>
              ))}
            </div>
          )}
          {scenario && (
            <div className="text-xs space-y-0.5 border-t border-amber-200 pt-2">
              <div className="flex justify-between">
                <span className="text-reasoner-body">Projected annual decline of replaced products</span>
                <span className="font-mono tabular-nums text-reasoner-red">-{scenario.decline}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-reasoner-body">New product estimated Year 1 revenue</span>
                <span className="font-mono tabular-nums text-reasoner-green">+{scenario.newRevenue}</span>
              </div>
              <div className="flex justify-between font-semibold border-t border-amber-300 pt-1">
                <span className="text-reasoner-ink">Net incremental category improvement</span>
                <span className={`font-mono tabular-nums ${scenario.net.toLowerCase().includes("positive") ? "text-reasoner-green" : "text-reasoner-red"}`}>
                  {scenario.net}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {vendorRisks.length > 0 && (
        <div className="bg-reasoner-bg border border-reasoner-line rounded-lg p-3">
          <h4 className="text-[10px] font-mono font-semibold text-reasoner-body mb-2 tracking-[0.1em]">VENDOR RELATIONSHIP RISKS</h4>
          <div className="space-y-1">
            {vendorRisks.map((vr, i) => (
              <div key={i} className="text-xs flex items-start gap-2">
                <span className={`inline-block text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded shrink-0 tracking-[0.05em] ${tierBadgeColor(vr.tier)}`}>
                  {vr.tier}
                </span>
                <span>
                  <span className="font-medium text-reasoner-ink">{vr.vendor}</span>
                  <span className="text-reasoner-body"> · {vr.detail}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
