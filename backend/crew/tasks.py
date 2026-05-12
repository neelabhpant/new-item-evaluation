from crewai import Agent, Task


def _format_enriched_products(data_package: dict) -> str:
    products = data_package.get("enriched_products", [])
    if not products:
        return "  (none found)"
    lines = []
    for i, p in enumerate(products, 1):
        lines.append(
            f"PRODUCT {i}: {p['name']} (SKU: {p['sku']})\n"
            f"  Similarity: {p['similarity_score']:.0%} | Brand: {p['brand']} | Category: {p['category']}\n"
            f"  Claims: {p.get('claims', 'N/A')}\n"
            f"  Revenue: ${p['annual_revenue']:,.0f}/yr | Units: {p['weekly_units']}/wk | Velocity Rank: #{p['velocity_rank']}\n"
            f"  YoY Growth: {p['yoy_growth']:+.1f}% | Trend: {p['trend']} | Status: {p['status']}\n"
            f"  Price: ${p['price']:.2f} | Margin: {p['margin_pct']:.1f}% | Shelf: {p['shelf_position']}\n"
            f"  Vendor ({p['brand']}): Fill Rate {p['vendor_fill_rate']:.1f}% | OTIF {p['vendor_otif_score']:.1f}% "
            f"| Tier: {p['vendor_relationship_tier']}"
        )
    return "\n\n".join(lines)


def _format_competing_vendors_summary(data_package: dict) -> str:
    products = data_package.get("enriched_products", [])
    if not products:
        return "  (no competing vendors)"
    vendor_products: dict[str, list] = {}
    for p in products:
        brand = p.get("brand", "Unknown")
        if brand not in vendor_products:
            vendor_products[brand] = []
        vendor_products[brand].append(p)
    lines = []
    for brand, prods in vendor_products.items():
        tier = prods[0].get("vendor_relationship_tier", "Unknown")
        fill = prods[0].get("vendor_fill_rate", 0)
        otif = prods[0].get("vendor_otif_score", 0)
        total_rev = sum(p["annual_revenue"] for p in prods)
        lines.append(
            f"  {brand} ({tier}): {len(prods)} product(s), "
            f"combined ${total_rev:,.0f}/yr, Fill Rate {fill:.1f}%, OTIF {otif:.1f}%"
        )
    return "\n".join(lines)


def _format_category_benchmarks(data_package: dict) -> str:
    cb = data_package.get("category_benchmarks", {})
    if not cb:
        return "  (no category benchmarks available)"
    return (
        f"  Category: {cb.get('category', 'N/A')}\n"
        f"  Market Size: ${cb.get('market_size', 0):,.0f}\n"
        f"  YoY Growth: {cb.get('yoy_growth', 0):.1f}%\n"
        f"  Avg Margin: {cb.get('avg_margin', 0):.1f}%\n"
        f"  Avg Price: ${cb.get('avg_price', 0):.2f}\n"
        f"  SKU Count: {cb.get('sku_count', 0)}\n"
        f"  Top Trend: {cb.get('top_trend', 'N/A')}"
    )


def _format_vendor_info(data_package: dict) -> str:
    vi = data_package.get("vendor_info", {})
    if not vi:
        return "  (no vendor data available)"
    return (
        f"  Vendor: {vi.get('vendor_name', 'N/A')}\n"
        f"  Fill Rate: {vi.get('fill_rate', 0):.1f}%\n"
        f"  OTIF Score: {vi.get('otif_score', 0):.1f}%\n"
        f"  Compliance Rating: {vi.get('compliance_rating', 'N/A')}\n"
        f"  Open Chargebacks: {vi.get('open_chargebacks', 0)}\n"
        f"  Relationship Tier: {vi.get('relationship_tier', 'N/A')}"
    )


def _format_adjacent_benchmarks(data_package: dict) -> str:
    benchmarks = data_package.get("adjacent_benchmarks", [])
    if not benchmarks:
        return "  (no adjacent category benchmarks available)"
    lines = []
    for b in benchmarks:
        lines.append(
            f"  {b['category']}: Market ${b['market_size']:,.0f}, "
            f"Growth {b['yoy_growth']:+.1f}%, "
            f"Avg Margin {b['avg_margin']:.1f}%, "
            f"Avg Price ${b['avg_price']:.2f}, "
            f"SKUs: {b['sku_count']}, "
            f"Trend: {b['top_trend']}"
        )
    return "\n".join(lines)


def _format_category_groups_summary(data_package: dict) -> str:
    groups = data_package.get("category_groups", [])
    if not groups:
        return "  (no category groups)"
    lines = []
    for g in groups:
        lines.append(
            f"  {g['category']}: {g['count']} product(s), "
            f"max similarity {g['max_similarity']:.0%}"
        )
    return "\n".join(lines)


def _format_submission(data_package: dict) -> str:
    sub = data_package["submission"]
    claims = sub.get("claims", [])
    claims_str = ", ".join(claims) if isinstance(claims, list) else str(claims)
    return (
        f"  Name: {sub['name']}\n"
        f"  Description: {sub.get('description', 'N/A')}\n"
        f"  Price: ${sub['price']:.2f}\n"
        f"  Category: {sub['category']}\n"
        f"  Claims: {claims_str}\n"
        f"  Brand: {sub.get('brand', 'N/A')}"
    )


def risk_market_task(agent: Agent, data_package: dict) -> Task:
    is_white_space = data_package["overlap_classification"] == "White Space"

    inferred_cat = data_package.get("inferred_category", "")

    if is_white_space:
        description = (
            "Evaluate the proposed new product as a NEW CATEGORY OPPORTUNITY. "
            "This product has been classified as White Space -- there are NO closely matching products "
            "in our current catalog. The products shown below are from DIFFERENT categories and are "
            "provided as informational reference only. They are NOT direct competitors and should NOT "
            "be analyzed for cannibalization risk.\n\n"
            "=== PROPOSED PRODUCT ===\n"
            f"{_format_submission(data_package)}\n\n"
            f"Overlap Classification: {data_package['overlap_classification']}\n"
            f"Auto-detected nearest category: {inferred_cat}\n\n"
            "=== CROSS-CATEGORY SIMILARITY RESULTS ===\n"
            f"{_format_category_groups_summary(data_package)}\n\n"
            "=== REFERENCE PRODUCTS (from other categories -- NOT direct competitors) ===\n"
            f"{_format_enriched_products(data_package)}\n\n"
            "=== CATEGORY BENCHMARKS (detected category) ===\n"
            f"{_format_category_benchmarks(data_package)}\n\n"
            "=== ADJACENT CATEGORY BENCHMARKS ===\n"
            f"{_format_adjacent_benchmarks(data_package)}\n\n"
            "Your analysis MUST cover:\n"
            "1. OPPORTUNITY TYPE: Is this a New Category entry, a Category Extension, or a Niche Play?\n"
            "2. MARKET OPPORTUNITY: Assess the size and attractiveness of this opportunity. "
            "What consumer need does this product fill that our current assortment does not?\n"
            "3. NEAREST CATEGORIES: Use the ADJACENT CATEGORY BENCHMARKS above to identify the 2-3 most "
            "relevant existing categories. What can we learn from their market size, growth rates, margins, "
            "and velocity to set realistic expectations for this new category?\n"
            "4. DEMAND SIGNALS: What evidence exists for consumer demand? Consider trends in adjacent "
            "categories, broader market trends (health, sustainability, convenience), and the product's claims.\n"
            "5. NET CATEGORY IMPACT: Since this is incremental (no cannibalization), estimate the new "
            "revenue this category could bring. Use adjacent category benchmarks to project realistic "
            "velocity and revenue for a new entrant.\n"
            "6. MARKET TIMING: Early (ahead of trends), On-Trend, or Late (plateauing).\n"
            "7. TREND ALIGNMENT: How well do the product's claims align with current consumer trends?"
        )
        expected_output = (
            "Return your analysis in this EXACT format with these EXACT labels. "
            "Do NOT use markdown formatting (no ** or * markers).\n\n"
            "REASONING: [2 short sentences. Sound like an experienced category buyer talking, not a report. "
            "Start with a concrete observation, not a framing sentence. "
            "Reference at least one specific number AND one specific SKU or brand from the data above. "
            "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'This evaluation shows'. "
            "DO NOT use phrases like 'the overlap classification', 'a crowded marketplace', 'well-established competition', 'market share'. "
            "Example style: 'Twenty protein bars already on the shelf, three of them putting up stable $200K-$650K revenue. Adding another bar in that lane splits what KIND and Nature Valley are already earning.']\n"
            "RISK_RATING: LOW\n"
            "OPPORTUNITY_TYPE: [New Category or Category Extension or Niche Play]\n"
            "MARKET_OPPORTUNITY: [1-3 sentence assessment of the market opportunity]\n"
            "NEAREST_CATEGORIES: [list the 2-3 closest existing categories and key learnings from each]\n"
            "DEMAND_SIGNALS: [evidence of consumer demand -- trends, adjacent category growth, claims alignment]\n"
            "CANNIBALIZATION_DETAILS:\n"
            "- NONE (White Space -- no directly competing products in catalog)\n"
            "UNDERPERFORMERS:\n"
            "- NONE\n"
            "REPLACEMENT_CANDIDATES:\n"
            "- NONE\n"
            "VENDOR_RISKS:\n"
            "- NONE\n"
            "NET_CATEGORY_IMPACT: positive $[X] estimated annual new category revenue\n"
            "CATEGORY: [proposed category name]\n"
            "CATEGORY_GROWTH: [X]% YoY (estimated from adjacent categories)\n"
            "MARKET_TIMING: [Early or On-Trend or Late]\n"
            "TOP_TREND: [trend description]"
        )
    else:
        description = (
            "Analyze the proposed new product against existing assortment data to assess "
            "cannibalization risk at the INDIVIDUAL SKU LEVEL and evaluate market context.\n\n"
            "=== PROPOSED PRODUCT ===\n"
            f"{_format_submission(data_package)}\n\n"
            f"Overlap Classification: {data_package['overlap_classification']}\n\n"
            "=== COMPETING PRODUCTS (similarity + sales + vendor data per SKU) ===\n"
            f"{_format_enriched_products(data_package)}\n\n"
            "=== COMPETING VENDORS SUMMARY ===\n"
            f"{_format_competing_vendors_summary(data_package)}\n\n"
            "=== CATEGORY BENCHMARKS ===\n"
            f"{_format_category_benchmarks(data_package)}\n\n"
            "IMPORTANT -- Overlap Classification context:\n"
            "- 'High Overlap' (>88% similarity) means VERY similar products already exist. The category "
            "is likely saturated for this product type. Set RISK_RATING to HIGH unless multiple existing "
            "products are clearly underperforming (declining, clearance). A new product in a crowded "
            "segment will cannibalize existing sales.\n"
            "- 'Moderate Overlap' (82-88% similarity) means partial overlap. Assess carefully per SKU. "
            "Set RISK_RATING to MEDIUM unless clear differentiation exists.\n\n"
            "Your analysis MUST cover:\n"
            "1. PER-SKU CANNIBALIZATION: For EACH competing product, rate its individual risk (Low/Medium/High) "
            "based on similarity score, revenue, trend, and price proximity. Estimate the dollar amount at risk "
            "for each product (percentage of its annual revenue that could shift to the new product).\n"
            "2. UNDERPERFORMER IDENTIFICATION: Flag products that are declining, on clearance, low velocity, "
            "or bottom-shelf as potential REPLACEMENT candidates. These are products we could deauthorize "
            "in favor of the new product.\n"
            "3. REPLACEMENT SCENARIO: Identify 0-3 specific declining products that the new product could replace. "
            "For each replacement candidate, calculate its PROJECTED ANNUAL DECLINE = current revenue x negative YoY growth rate. "
            "This is revenue the category is ALREADY LOSING regardless of what we do. "
            "Then estimate the new product's Year 1 revenue using the MEDIAN weekly units of comparable products "
            "(adjusted down 20-30% for new market entry) x the proposed price x 52 weeks. "
            "The net incremental impact = new product revenue vs the projected decline. "
            "IMPORTANT: Do NOT use the full revenue of replaced products as 'revenue lost'. "
            "The replaced products' customers don't vanish -- most migrate to the new product or other category items. "
            "Only the PROJECTED DECLINE amount represents true category erosion.\n"
            "4. VENDOR RELATIONSHIP RISK: For each vendor whose products might be replaced, note their "
            "relationship tier. Flag Strategic/Preferred vendors where replacement could damage the relationship.\n"
            "5. NET CATEGORY IMPACT: Will this product grow the category or just redistribute sales?\n"
            "6. MARKET TIMING: Early (ahead of trends), On-Trend, or Late (plateauing).\n"
            "7. TREND ALIGNMENT: How well do the product's claims align with the category's top trend?"
        )
        expected_output = (
            "Return your analysis in this EXACT format with these EXACT labels. "
            "Do NOT use markdown formatting (no ** or * markers).\n\n"
            "REASONING: [2 short sentences. Sound like an experienced category buyer talking, not a report. "
            "Start with a concrete observation, not a framing sentence. "
            "Reference at least one specific number AND one specific SKU or brand from the data above. "
            "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'This evaluation shows'. "
            "DO NOT use phrases like 'the overlap classification', 'a crowded marketplace', 'well-established competition', 'market share'. "
            "Example style: 'Twenty protein bars already on the shelf, three of them putting up stable $200K-$650K revenue. Adding another bar in that lane splits what KIND and Nature Valley are already earning.']\n"
            "RISK_RATING: [LOW or MEDIUM or HIGH]\n"
            "CANNIBALIZATION_DETAILS:\n"
            "- [SKU] [Product name]: [X]% similar, $[revenue]/yr, [trend], [risk level] risk, est. $[X] at risk\n"
            "- (one line per competing product)\n"
            "UNDERPERFORMERS:\n"
            "- [SKU] [Product name]: [reason - e.g. declining -5.2% YoY, bottom shelf, clearance]\n"
            "- (one line per underperformer, or NONE if all are performing well)\n"
            "REPLACEMENT_CANDIDATES:\n"
            "- REPLACE [SKU] [Product name] ($[revenue]/yr, [trend]) -- Reason: [why this should be replaced]\n"
            "- (0-3 candidates, or NONE)\n"
            "REPLACEMENT_PROJECTED_DECLINE: $[X] annual (total projected YoY revenue loss of replaced products -- calculated as each replaced product's revenue x its negative YoY rate. This revenue is being lost by the category regardless.)\n"
            "REPLACEMENT_NEW_PRODUCT_REVENUE: $[X] annual (estimated Year 1 revenue of new product, using comparable velocity x proposed price x 52 weeks, adjusted down 20-30% for new entry. NEVER put $0 here.)\n"
            "REPLACEMENT_NET_INCREMENTAL: [positive or negative] $[X] annual improvement to category health (new product revenue minus projected decline)\n"
            "VENDOR_RISKS:\n"
            "- [Vendor name] ([tier]): [X] product(s) affected, [risk assessment]\n"
            "- (one line per affected vendor, or NONE)\n"
            "NET_CATEGORY_IMPACT: [positive or negative] $[amount] estimated annual impact\n"
            "CATEGORY: [category name]\n"
            "CATEGORY_GROWTH: [X]% YoY\n"
            "MARKET_TIMING: [Early or On-Trend or Late]\n"
            "TOP_TREND: [trend description]"
        )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )


def financial_task(agent: Agent, data_package: dict, context: list[Task]) -> Task:
    is_white_space = data_package["overlap_classification"] == "White Space"
    sub = data_package["submission"]

    if is_white_space:
        description = (
            "Project Year 1 financial performance for a NEW CATEGORY product entry. "
            "This product has been classified as White Space -- there are no directly competing products "
            "in our catalog, so there is ZERO cannibalization risk.\n\n"
            "=== PROPOSED PRODUCT ===\n"
            f"{_format_submission(data_package)}\n\n"
            "=== REFERENCE PRODUCTS (from other categories -- for velocity benchmarking only) ===\n"
            f"{_format_enriched_products(data_package)}\n\n"
            "=== CATEGORY BENCHMARKS (detected category) ===\n"
            f"{_format_category_benchmarks(data_package)}\n\n"
            "=== ADJACENT CATEGORY BENCHMARKS ===\n"
            f"{_format_adjacent_benchmarks(data_package)}\n\n"
            "=== SUBMITTED PRODUCT'S VENDOR SCORECARD ===\n"
            f"{_format_vendor_info(data_package)}\n\n"
            "Use the Risk & Market Analyst's opportunity assessment from the previous task.\n\n"
            "IMPORTANT: This is a NEW CATEGORY entry. There is NO cannibalization. "
            "All revenue from this product is 100% INCREMENTAL to the retailer.\n\n"
            "IMPORTANT: Revenue projections MUST be ANNUAL (weekly units x price x 52 weeks). "
            "Use adjacent category benchmarks to set realistic velocity expectations. "
            "Look at the average weekly units and prices in the most similar adjacent categories, "
            "then adjust DOWN 30-50% since this is a brand new category with no "
            "established demand in our stores.\n\n"
            "Your financial model must include:\n"
            f"1. VELOCITY ESTIMATE: Conservative estimate for new category entry. Use the ADJACENT CATEGORY "
            f"BENCHMARKS above to find comparable velocity ranges, then adjust down for new category risk.\n"
            f"2. REVENUE PROJECTION: Weekly units x ${sub['price']:.2f} x 52 weeks for ANNUAL revenue.\n"
            "3. THREE SCENARIOS: First compute Expected = WEEKLY_UNITS x $"
            f"{sub['price']:.2f} x 52 weeks. "
            "Then Best case = Expected x 1.20 (20% higher velocity). "
            "Worst case = Expected x 0.70 (30% lower velocity). "
            "All three values MUST be different numbers.\n"
            "4. MARGIN CONTRIBUTION: Using average margin from adjacent categories.\n"
            "5. RAMP ASSUMPTION: New categories typically take 3-6 months to reach steady-state velocity. "
            "Describe your Year 1 ramp expectation (e.g., 50% velocity in Q1-Q2, full velocity Q3-Q4).\n"
            "6. NET INCREMENTAL REVENUE: 100% of projected revenue is incremental (no cannibalization offset)."
        )
        expected_output = (
            "Return your projection in this EXACT format with these EXACT labels. "
            "Do NOT use markdown formatting (no ** or * markers).\n\n"
            "REASONING: [2 short sentences on your financial approach. Sound like a buyer doing back-of-envelope math, not a consultant. "
            "Start with the comparable product or anchor you used, not a framing sentence. "
            "Reference at least one specific number AND one specific SKU or brand from the data above. "
            "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'Based on the data'. "
            "DO NOT use phrases like 'the overlap classification', 'market share', 'revenue stream'. "
            "Example style: 'RXBAR is the closest comparable at 500 units per week and $5.49. I knocked 25% off for new-entry drag and landed on $368K Year 1 expected.']\n"
            "WEEKLY_UNITS: [X] units/week (expected -- conservative new category estimate)\n"
            "BEST_CASE: $[X] annual revenue\n"
            "EXPECTED: $[X] annual revenue\n"
            "WORST_CASE: $[X] annual revenue\n"
            "MARGIN: [X]%\n"
            "CANNIBALIZATION_BREAKDOWN:\n"
            "- NONE (White Space -- no cannibalization expected)\n"
            "CANNIBALIZATION_OFFSET: $0 annual\n"
            "NET_INCREMENTAL: $[X] annual (100% incremental -- new category)\n"
            "RAMP_ASSUMPTION: [description of Year 1 ramp-up expectations, e.g. 50% velocity months 1-6, full velocity months 7-12]\n"
            "VENDOR_IMPACT:\n"
            "- NONE\n"
            "VENDOR_RELIABILITY: [one sentence assessment of submitted product's vendor supply chain reliability]"
        )
    else:
        description = (
            "Project Year 1 financial performance for the proposed new product, including "
            "per-SKU cannibalization breakdown and replacement scenario financials.\n\n"
            "=== PROPOSED PRODUCT ===\n"
            f"{_format_submission(data_package)}\n\n"
            "=== COMPETING PRODUCTS (similarity + sales + vendor data per SKU) ===\n"
            f"{_format_enriched_products(data_package)}\n\n"
            "=== CATEGORY BENCHMARKS ===\n"
            f"{_format_category_benchmarks(data_package)}\n\n"
            "=== SUBMITTED PRODUCT'S VENDOR SCORECARD ===\n"
            f"{_format_vendor_info(data_package)}\n\n"
            "Use the Risk & Market Analyst's per-SKU cannibalization assessment and replacement candidates "
            "from the previous task to build your financial model.\n\n"
            "IMPORTANT: Revenue projections MUST be ANNUAL (weekly units x price x 52 weeks). "
            "Use the actual revenue figures shown in the competing products data above as benchmarks.\n\n"
            "Your financial model must include:\n"
            f"1. VELOCITY ESTIMATE: Based on comparable products' weekly units (typically 50-2000 units/week), "
            f"adjusted down 20-30% for new market entry.\n"
            f"2. REVENUE PROJECTION: Weekly units x ${sub['price']:.2f} x 52 weeks for ANNUAL revenue.\n"
            "3. THREE SCENARIOS: First compute Expected = WEEKLY_UNITS x $"
            f"{sub['price']:.2f} x 52 weeks. "
            "Then Best case = Expected x 1.20 (20% higher velocity). "
            "Worst case = Expected x 0.70 (30% lower velocity). "
            "All three values MUST be different numbers.\n"
            "4. MARGIN CONTRIBUTION: Using category average margin.\n"
            "5. PER-SKU CANNIBALIZATION BREAKDOWN: For each competing product the Risk Analyst flagged, "
            "estimate the dollar revenue impact (how much of that SKU's revenue shifts to the new product).\n"
            "6. REPLACEMENT SCENARIO: If the Risk Analyst identified replacement candidates, calculate: "
            "projected annual decline of each replaced product (revenue x negative YoY rate -- this is money the category "
            "is already losing), new product revenue, and net incremental category improvement. "
            "Do NOT use full revenue of replaced products as 'lost' -- their customers mostly migrate to the new product.\n"
            "7. VENDOR IMPACT: For each vendor whose products may be replaced, note the financial and "
            "relationship impact. Flag Strategic/Preferred vendors.\n"
            "8. NET INCREMENTAL REVENUE: Revenue minus cannibalization offset."
        )
        expected_output = (
            "Return your projection in this EXACT format with these EXACT labels. "
            "Do NOT use markdown formatting (no ** or * markers).\n\n"
            "REASONING: [2 short sentences on your financial approach. Sound like a buyer doing back-of-envelope math, not a consultant. "
            "Start with the comparable product or anchor you used, not a framing sentence. "
            "Reference at least one specific number AND one specific SKU or brand from the data above. "
            "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'Based on the data'. "
            "DO NOT use phrases like 'the overlap classification', 'market share', 'revenue stream'. "
            "Example style: 'RXBAR is the closest comparable at 500 units per week and $5.49. I knocked 25% off for new-entry drag and landed on $368K Year 1 expected.']\n"
            "WEEKLY_UNITS: [X] units/week (expected)\n"
            "BEST_CASE: $[X] annual revenue\n"
            "EXPECTED: $[X] annual revenue\n"
            "WORST_CASE: $[X] annual revenue\n"
            "MARGIN: [X]%\n"
            "CANNIBALIZATION_BREAKDOWN:\n"
            "- [SKU] [Product name]: est. -$[X]/yr revenue impact\n"
            "- (one line per affected product)\n"
            "CANNIBALIZATION_OFFSET: $[X] annual (total)\n"
            "NET_INCREMENTAL: $[X] annual (expected scenario)\n"
            "REPLACEMENT_SCENARIO:\n"
            "- Replace [SKU] [name]: declining at [X]% YoY, projected annual loss -$[X]\n"
            "- (list each replacement with its projected decline)\n"
            "- New product expected: +$[X]/yr\n"
            "- Net incremental category improvement: [positive or negative] $[X]/yr\n"
            "VENDOR_IMPACT:\n"
            "- [Vendor] ([tier]): losing [X] SKU(s), $[X]/yr revenue at risk, relationship risk [LOW/MEDIUM/HIGH]\n"
            "- (one line per affected vendor, or NONE)\n"
            "VENDOR_RELIABILITY: [one sentence assessment of submitted product's vendor supply chain reliability]"
        )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context,
    )


def recommendation_task(agent: Agent, data_package: dict, context: list[Task]) -> Task:
    is_white_space = data_package["overlap_classification"] == "White Space"
    predetermined_verdict = data_package.get("predetermined_verdict", "AUTHORIZE")
    predetermined_confidence = data_package.get("predetermined_confidence", 70)

    if is_white_space:
        description = (
            "Synthesize all previous analysis into a final recommendation report for this "
            "NEW CATEGORY opportunity.\n\n"
            "=== PROPOSED PRODUCT ===\n"
            f"{_format_submission(data_package)}\n\n"
            f"Overlap Classification: {data_package['overlap_classification']}\n\n"
            "Review the Risk & Market Analyst's opportunity assessment and the Financial Modeler's "
            "projections from previous tasks.\n\n"
            f"=== PREDETERMINED VERDICT ===\n"
            f"The evaluation system has determined the verdict: {predetermined_verdict}\n"
            f"Confidence: {predetermined_confidence}%\n\n"
            "YOUR ROLE: You do NOT decide the verdict. The verdict above is final and determined by "
            "the evaluation system's decision matrix based on overlap classification and category data. "
            "Your job is to:\n"
            "1. Synthesize the top 3 reasons that SUPPORT this verdict using evidence from the "
            "Risk & Market Analyst and Financial Modeler outputs.\n"
            "2. Provide actionable details: retail price suggestion, shelf placement, store rollout.\n"
            "3. There are NO products to replace -- all revenue is incremental.\n\n"
            "IMPORTANT: Your output MUST use the exact verdict and confidence shown above. "
            "Do NOT change or override the verdict."
        )
        expected_output = (
            "Return your recommendation in this EXACT format with these EXACT labels. "
            "Do NOT use markdown formatting (no ** or * markers).\n\n"
            "REASONING: [2 short sentences synthesizing Risk and Financial into the verdict. Sound like a senior merchant speaking to a buyer, not a report. "
            "Start with the single strongest piece of evidence, not a framing sentence. "
            "Reference at least one specific number AND one specific SKU or brand from the data above. "
            "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'Synthesizing the findings'. "
            "DO NOT use phrases like 'the overlap classification', 'a crowded marketplace', 'well-established competition'. "
            "Example style: 'Three high-performing KIND and Nature Valley SKUs dominate this shelf and none are declining. Without a replacement candidate that moves the category, this does not earn a slot.']\n"
            f"VERDICT: {predetermined_verdict}\n"
            f"CONFIDENCE: {predetermined_confidence}%\n"
            "REASON_1: [first supporting reason - one sentence using evidence from previous agents]\n"
            "REASON_2: [second supporting reason - one sentence]\n"
            "REASON_3: [third supporting reason - one sentence]\n"
            "SUGGESTED_RETAIL: $[X.XX]\n"
            "PLACEMENT: [shelf placement recommendation -- consider new section or endcap for new category]\n"
            "ROLLOUT: [number] stores initially (conservative for new category test)\n"
            "REPLACE_SKUS: NONE\n"
            "REPLACEMENT_NET_IMPACT: N/A"
        )
    else:
        sat = data_package.get("category_saturation", {})
        total_skus = sat.get("total_skus_in_category", 0)

        description = (
            "Synthesize all previous analysis into a final recommendation report, including specific "
            "SKU replacement actions and vendor strategy.\n\n"
            "=== PROPOSED PRODUCT ===\n"
            f"{_format_submission(data_package)}\n\n"
            f"Overlap Classification: {data_package['overlap_classification']}\n"
            f"Similar Products Found: {len(data_package.get('enriched_products', data_package.get('similar_products', [])))}\n"
            f"Total SKUs in category: {total_skus}\n\n"
            "Review the Risk & Market Analyst's per-SKU cannibalization assessment, replacement candidates, "
            "and the Financial Modeler's projections and replacement scenario from previous tasks.\n\n"
            f"=== PREDETERMINED VERDICT ===\n"
            f"The evaluation system has determined the verdict: {predetermined_verdict}\n"
            f"Confidence: {predetermined_confidence}%\n\n"
            "YOUR ROLE: You do NOT decide the verdict. The verdict above is final and determined by "
            "the evaluation system's decision matrix based on overlap classification and category data. "
            "Your job is to:\n"
            "1. Synthesize the top 3 reasons that SUPPORT this verdict using evidence from the "
            "Risk & Market Analyst and Financial Modeler outputs.\n"
            "2. Provide actionable details: retail price, shelf placement, store rollout count.\n"
            "3. If the verdict is AUTHORIZE or MODIFY, identify SKUs to replace from the Risk Analyst's candidates.\n"
            "4. If the verdict is DECLINE, explain why the category cannot absorb another SKU and "
            "provide specific supplier feedback on what would change the outcome.\n"
            "5. If the verdict is MODIFY, specify what changes are needed (price, positioning, claims, format).\n\n"
            "IMPORTANT: Your output MUST use the exact verdict and confidence shown above. "
            "Do NOT change or override the verdict."
        )

        if predetermined_verdict == "DECLINE":
            expected_output = (
                "Return your recommendation in this EXACT format with these EXACT labels. "
                "Do NOT use markdown formatting (no ** or * markers).\n\n"
                "REASONING: [2 short sentences synthesizing Risk and Financial into the verdict. Sound like a senior merchant speaking to a buyer, not a report. "
                "Start with the single strongest piece of evidence, not a framing sentence. "
                "Reference at least one specific number AND one specific SKU or brand from the data above. "
                "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'Synthesizing the findings'. "
                "DO NOT use phrases like 'the overlap classification', 'a crowded marketplace', 'well-established competition'. "
                "Example style: 'Three high-performing KIND and Nature Valley SKUs dominate this shelf and none are declining. Without a replacement candidate that moves the category, this does not earn a slot.']\n"
                f"VERDICT: DECLINE\n"
                f"CONFIDENCE: {predetermined_confidence}%\n"
                "REASON_1: [first reason supporting DECLINE - cite evidence from previous agents]\n"
                "REASON_2: [second reason supporting DECLINE]\n"
                "REASON_3: [third reason supporting DECLINE]\n"
                "SUGGESTED_RETAIL: N/A\n"
                "PLACEMENT: N/A\n"
                "ROLLOUT: 0 stores\n"
                "REPLACE_SKUS: NONE\n"
                "REPLACEMENT_NET_IMPACT: N/A"
            )
        elif predetermined_verdict == "MODIFY":
            expected_output = (
                "Return your recommendation in this EXACT format with these EXACT labels. "
                "Do NOT use markdown formatting (no ** or * markers).\n\n"
                "REASONING: [2 short sentences synthesizing Risk and Financial into the verdict. Sound like a senior merchant speaking to a buyer, not a report. "
                "Start with the single strongest piece of evidence, not a framing sentence. "
                "Reference at least one specific number AND one specific SKU or brand from the data above. "
                "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'Synthesizing the findings'. "
                "DO NOT use phrases like 'the overlap classification', 'a crowded marketplace', 'well-established competition'. "
                "Example style: 'Three high-performing KIND and Nature Valley SKUs dominate this shelf and none are declining. Without a replacement candidate that moves the category, this does not earn a slot.']\n"
                f"VERDICT: MODIFY\n"
                f"CONFIDENCE: {predetermined_confidence}%\n"
                "REASON_1: [first reason supporting MODIFY - what needs to change and why]\n"
                "REASON_2: [second reason supporting MODIFY]\n"
                "REASON_3: [third reason supporting MODIFY]\n"
                "SUGGESTED_RETAIL: $[X.XX] (adjusted price recommendation)\n"
                "PLACEMENT: [shelf placement recommendation if modifications are made]\n"
                "ROLLOUT: [number] stores for limited trial\n"
                "REPLACE_SKUS: [SKU1 Product Name, SKU2 Product Name] or NONE\n"
                "REPLACEMENT_NET_IMPACT: [positive or negative] $[X] annual incremental category improvement, or N/A"
            )
        else:
            expected_output = (
                "Return your recommendation in this EXACT format with these EXACT labels. "
                "Do NOT use markdown formatting (no ** or * markers).\n\n"
                "REASONING: [2 short sentences synthesizing Risk and Financial into the verdict. Sound like a senior merchant speaking to a buyer, not a report. "
                "Start with the single strongest piece of evidence, not a framing sentence. "
                "Reference at least one specific number AND one specific SKU or brand from the data above. "
                "DO NOT start with 'In analyzing', 'I found that', 'After reviewing', 'The analysis indicates', or 'Synthesizing the findings'. "
                "DO NOT use phrases like 'the overlap classification', 'a crowded marketplace', 'well-established competition'. "
                "Example style: 'Three high-performing KIND and Nature Valley SKUs dominate this shelf and none are declining. Without a replacement candidate that moves the category, this does not earn a slot.']\n"
                f"VERDICT: AUTHORIZE\n"
                f"CONFIDENCE: {predetermined_confidence}%\n"
                "REASON_1: [first reason supporting AUTHORIZE - cite evidence from previous agents]\n"
                "REASON_2: [second reason supporting AUTHORIZE]\n"
                "REASON_3: [third reason supporting AUTHORIZE]\n"
                "SUGGESTED_RETAIL: $[X.XX]\n"
                "PLACEMENT: [shelf placement recommendation]\n"
                "ROLLOUT: [number] stores initially\n"
                "REPLACE_SKUS: [SKU1 Product Name, SKU2 Product Name] or NONE\n"
                "REPLACEMENT_NET_IMPACT: [positive or negative] $[X] annual incremental category improvement, or N/A"
            )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context,
    )
