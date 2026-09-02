# New Item Evaluation Platform — Technical Documentation

A complete end-to-end technical reference for the New Item Evaluation Platform. This document is written so a technical engineer can read it cold and set the system up from scratch — from catalog acquisition through to running the three reasoning agents — without needing the original author.

---

## Table of Contents

1. [What This System Does](#1-what-this-system-does)
2. [Architectural Overview](#2-architectural-overview)
3. [Phase 0 — Catalog Bootstrap (one-time)](#3-phase-0--catalog-bootstrap-one-time)
   - [3.1 Download the catalog from Open Food Facts](#31-download-the-catalog-from-open-food-facts)
   - [3.2 Assign categories](#32-assign-categories)
   - [3.3 Create the OpenSearch index](#33-create-the-opensearch-index)
   - [3.4 Generate CLIP embeddings and index](#34-generate-clip-embeddings-and-index)
   - [3.5 Seed DuckDB with synthetic retail data](#35-seed-duckdb-with-synthetic-retail-data)
4. [Phase 1 — Deterministic Submission Pipeline](#4-phase-1--deterministic-submission-pipeline)
   - [4.1 Embed the submission](#41-embed-the-submission)
   - [4.2 Cross-category k-NN search](#42-cross-category-k-nn-search)
   - [4.3 Category auto-detection](#43-category-auto-detection)
   - [4.4 Overlap classification](#44-overlap-classification)
   - [4.5 Enrich with sales, vendor, and benchmark data](#45-enrich-with-sales-vendor-and-benchmark-data)
   - [4.6 Category saturation](#46-category-saturation)
5. [Phase 2 — Deterministic Verdict Engine](#5-phase-2--deterministic-verdict-engine)
6. [Phase 3 — Agentic Reasoning (CrewAI)](#6-phase-3--agentic-reasoning-crewai)
   - [6.1 Agent 1: Risk & Market Analyst](#61-agent-1-risk--market-analyst)
   - [6.2 Agent 2: Financial Modeler](#62-agent-2-financial-modeler)
   - [6.3 Agent 3: Recommendation Synthesizer](#63-agent-3-recommendation-synthesizer)
7. [Phase 4 — Final Output Assembly](#7-phase-4--final-output-assembly)
8. [Real-Time WebSocket Protocol](#8-real-time-websocket-protocol)
9. [API Reference](#9-api-reference)
10. [Frontend Architecture](#10-frontend-architecture)
11. [End-to-End Setup Guide](#11-end-to-end-setup-guide)
12. [Architectural Decisions & FAQ](#12-architectural-decisions--faq)
13. [Cloudera AI Deployment](#13-cloudera-ai-deployment)

---

## 1. What This System Does

A supplier submits a new CPG/Grocery product to a retailer for assortment authorization. The submission carries:

- A product image (JPG/PNG)
- Product name, description, proposed retail price
- A category (user-selected, or "Auto-detect")
- Marketing claims (e.g. "Organic", "Non-GMO", "Gluten-Free")

The system answers three questions in roughly 30–45 seconds:

1. **What in our existing assortment does this look like?** — multimodal similarity search using CLIP embeddings indexed in OpenSearch.
2. **What is the financial impact of adding it?** — projected Year-1 revenue + margin, minus cannibalization of existing SKUs.
3. **Should we authorize it?** — AUTHORIZE / MODIFY / DECLINE with confidence score and supporting evidence.

The differentiator is the **multimodal** part: the system sees the product image, not just its text description. Two products with totally different packaging but identical ingredients lists score lower than two products with similar packaging from different brands.

---

## 2. Architectural Overview

The runtime pipeline is split into two halves:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DETERMINISTIC DATA COLLECTION (2–3 seconds, no LLM)                 │
│                                                                              │
│  Submission ──► CLIP embed ──► OpenSearch k-NN ──► DuckDB enrich            │
│                                       │                                      │
│                                       ▼                                      │
│                              DataPackage (dict)                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ DETERMINISTIC VERDICT ENGINE (1 ms)                                          │
│   compute_verdict(DataPackage) → (verdict, confidence)                       │
│   Injected back into DataPackage BEFORE the agents run.                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: AGENTIC REASONING (CrewAI sequential, ~30–45 s)                     │
│                                                                              │
│  Agent 1: Risk & Market Analyst        — reads DataPackage                   │
│  Agent 2: Financial Modeler            — reads DataPackage + Agent 1         │
│  Agent 3: Recommendation Synthesizer   — reads DataPackage + Agent 1 + 2     │
│                                                                              │
│  Each agent has tools=[]. They reason over data injected into the task       │
│  description string. No tool calls. No web access.                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ POST-PROCESS                                                                  │
│   • Financial scenario fix (Best = Expected×1.20, Worst = Expected×0.70)     │
│   • Verdict override — always reassert compute_verdict() result              │
│   • Persist to DuckDB evaluation_history                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                          UI (WebSocket streamed)
```

**Why hybrid?** Generating an embedding, hitting OpenSearch, and querying DuckDB are mechanical operations. Wrapping them in an LLM tool-call loop adds 10–30 seconds per call, costs tokens, and introduces hallucination risk on tool arguments. The deterministic phase is faster and more reliable; the LLMs are reserved for *reasoning over* the collected data, which is what they are good at.

**Why is the verdict deterministic?** Buyers want auditable decisions. Identical inputs must produce identical verdicts. An LLM "deciding" the verdict produces drift across runs. The matrix in `compute_verdict()` is auditable, debuggable, and explainable to a category manager.

---

## 3. Phase 0 — Catalog Bootstrap (one-time)

Before any submission can be evaluated, the system needs:

- A catalog of products with images, metadata, and categories
- An OpenSearch index containing CLIP embeddings of every catalog product
- A DuckDB store with synthetic sales / vendor / category-benchmark data

The four bootstrap scripts in `scripts/` plus `backend/data/init_db.py` produce all of this. Run order matters.

### 3.1 Download the catalog from Open Food Facts

**Script:** `scripts/download_catalog.py`

Pulls snack-category products from the public Open Food Facts API. Iterates through 20 snack categories (protein bar, granola bar, trail mix, popcorn, etc.) and for each one fetches up to 20 US products. For each product it downloads:

- Front-facing product image → `data/images/catalog/{barcode}.jpg`
- Metadata (name, brands, ingredients, labels, nutriments) → appended to `data/catalog_products.json`

Each record gets a `local_image_path` field pointing at the downloaded JPG. The script deduplicates by barcode, skips products without images, and rate-limits at 2 seconds per category to be polite to Open Food Facts.

**Output:** ~200–300 product images plus a JSON file with their metadata. The exact count varies because Open Food Facts adds and removes products over time.

```bash
python scripts/download_catalog.py
```

### 3.2 Assign categories

**Script:** `scripts/assign_categories.py`

Open Food Facts categories are messy ("Plant-based foods and beverages, Beverages, Snacks, ..."). The system needs a clean, low-cardinality category set so OpenSearch can filter and DuckDB benchmarks can join.

Two-pass keyword classifier:

1. **Primary pass** (lines 20–43 of the script). Regex rules on the product name. For example, `protein bar|protein` → `"Protein Bars"`, `tortilla chip|tortilla` → `"Tortilla Chips"`. Anything unmatched falls into `"Other Snacks"`.
2. **Rescue pass** (lines 44–62). For items still in `"Other Snacks"`, brand-aware rules. For example, `rxbar|iq bar|clif` → `"Protein Bars"`, `late july|sun chips|harvest snaps` → `"Veggie Snacks"`. A few items (e.g. `granulated garlic`) are tagged `REMOVE` and dropped — they're not snacks at all.

Each product gets a `category_assigned` field. The script overwrites `data/catalog_products.json` in place.

**Final category set:** Protein Bars, Granola Bars, Trail Mix, Tortilla Chips, Potato Chips, Veggie Snacks, Popcorn, Rice Cakes, Fruit Snacks, Energy Bars, Pretzels, Crackers, Chocolate & Candy, Yogurt Snacks, Cheese Snacks, Puffed Snacks, Nut Bars, Cookies, Chips, Snack Bars, Other Snacks. ~20 categories total.

```bash
python scripts/assign_categories.py
```

### 3.3 Create the OpenSearch index

**Script:** `scripts/create_index.py`

Creates the `product-catalog` index with k-NN capability enabled. The mapping:

```json
{
  "settings": { "index": { "knn": true } },
  "mappings": {
    "properties": {
      "sku": { "type": "keyword" },
      "name": { "type": "text" },
      "description": { "type": "text" },
      "category": { "type": "keyword" },
      "brand": { "type": "keyword" },
      "price": { "type": "float" },
      "image_path": { "type": "keyword" },
      "ingredients": { "type": "text" },
      "claims": { "type": "keyword" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 512,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "lucene"
        }
      }
    }
  }
}
```

**Vector specifics:**

- **Dimension 512** — fixed by the CLIP ViT-B/32 model. Both image and text encoders output 512-dim vectors.
- **HNSW algorithm** — Hierarchical Navigable Small World. Approximate nearest neighbor; sub-millisecond queries at the cost of a small recall penalty (usually >95% recall at k=10).
- **Cosine similarity** — angle between vectors. Because the system L2-normalizes every embedding to unit length before storing, cosine similarity equals dot product, and the score returned by OpenSearch maps to `[0, 1]`.
- **Lucene engine** — OpenSearch supports lucene, nmslib, and faiss. Lucene is bundled and works out of the box.

The script is idempotent — it deletes the existing index first if present.

```bash
python scripts/create_index.py
```

### 3.4 Generate CLIP embeddings and index

**Script:** `scripts/index_catalog.py`

This is the heaviest bootstrap step. For each product in `data/catalog_products.json`:

1. **Load and preprocess the image** (224×224, ImageNet normalization)
2. **Build the "rich text" string** = `f"{name} {brand} {category_assigned} {key_ingredients}"`. Key ingredients are the first 8 tokens after stripping parentheticals and common fillers (salt, water, sugar, natural flavor, lecithin). This gives CLIP more semantic signal than `name + brand` alone — for example a "KIND Dark Chocolate Almond Bar" benefits enormously from having "almond" in the text.
3. **Encode separately**:
   - `img_emb = model.encode_image(image)` → 512-dim
   - `txt_emb = model.encode_text(tokenizer([rich_text]))` → 512-dim
4. **L2-normalize each**: `img_emb /= img_emb.norm()`, same for `txt_emb`
5. **Average them**: `combined = (img_emb + txt_emb) / 2`
6. **Re-normalize**: `combined /= combined.norm()` — final 512-dim unit vector
7. **POST to OpenSearch** with the doc fields and the embedding

**Why average image and text?** This is the classic "multimodal joint embedding" trick. CLIP was trained so that semantically matching image–text pairs sit close together in the same vector space. By averaging the two normalized vectors, the combined embedding encodes both *what the product looks like* (packaging, shape, color) and *what it is* (name, brand, category, ingredients). At query time, similarity scores reflect *both* visual and semantic match.

**Why not concatenate them into 1024 dims?** Concatenation requires the index to know which half of the vector to weight more, and forces the query vector to have the same layout. Averaging is simpler, preserves the 512-dim search space, and the unit-normalization ensures both modalities contribute equally.

**Time cost:** 5–10 minutes on CPU for ~250 products. Slower the first run because `torch` downloads the ~150 MB CLIP weights to `~/.cache/clip/`.

```bash
python scripts/index_catalog.py
```

### 3.5 Seed DuckDB with synthetic retail data

**Script:** `backend/data/init_db.py`

OpenSearch holds embeddings; DuckDB holds *retail business data*. The two are joined at evaluation time by SKU (barcode).

Four tables are seeded from `data/catalog_products.json` using a fixed random seed (`Random(42)`) so the data is reproducible:

**`products`** — one row per SKU.
```
sku, name, category, brand, price, cost, margin_pct, status, shelf_position,
authorized_date, image_path
```
- `price` drawn from category-specific ranges (Protein Bars: $3.00–$7.00, Trail Mix: $4.00–$8.00, etc.)
- `cost` = `price × random(0.40, 0.60)` — 40–60% COGS
- `margin_pct` = derived `(1 - cost_pct) × 100`
- `status` ∈ {active, clearance, seasonal, new} with active dominant (75%)
- `shelf_position` ∈ {eye-level, top, bottom, endcap}

**`sales_performance`** — one row per SKU.
```
sku, annual_revenue, weekly_units, velocity_rank, yoy_growth, stores_carrying, trend
```
- `weekly_units` ∈ [50, 2000] uniform
- **`annual_revenue` = `weekly_units × price × 52 × noise(0.85, 1.15)`** — this is the critical consistency invariant. Revenue is not drawn independently; it's *derived* from velocity and price. A $0.99 product cannot have $1M revenue.
- `yoy_growth` drawn from category-specific ranges (Veggie Snacks: 6–15%, Granola Bars: -2 to 5%), clamped to [-15, +30]
- `trend` derived from yoy_growth: `>5%` growing, `<-2%` declining, else stable
- `velocity_rank` = rank within category, sorted by weekly_units desc

**`category_benchmarks`** — one row per category.
```
category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend
```
- `market_size` drawn from category-specific ranges (Chocolate & Candy: $15–25B, Other Snacks: $500M–1.5B)
- `top_trend` is a hard-coded string per category (Protein Bars: "High-protein, clean-label ingredients")
- `sku_count` counted from catalog after seeding products

**`vendor_scorecard`** — one row per brand. Brands extracted from `products.brand`.
```
vendor_name, fill_rate, otif_score, compliance_rating, open_chargebacks, relationship_tier
```
- `fill_rate` ∈ [85, 99.5], `otif_score` ∈ [80, 99]
- `relationship_tier` correlated with score: `fill_rate > 95 AND otif > 92` → Strategic/Preferred, lower → Standard/Probationary
- `compliance_rating` ∈ {Excellent, Good, Fair, Needs Improvement}

**`evaluation_history`** — created lazily on first backend startup by `ensure_evaluation_history()`. Holds one row per completed evaluation; powers the History tab.

```bash
python backend/data/init_db.py
```

After this, the system is fully bootstrapped. Subsequent evaluations are read-only against this DuckDB plus the indexed OpenSearch documents.

---

## 4. Phase 1 — Deterministic Submission Pipeline

When `POST /api/evaluate` arrives, `backend/pipeline/orchestrator.py:run_evaluation()` kicks off `backend/pipeline/data_collector.py:collect_evaluation_data()`. This is plain Python — no LLM, no agents.

### 4.1 Embed the submission

**Module:** `backend/tools/embedding_client.py`

The CLIP model is loaded once at backend startup (singleton in `_get_clip()`) and reused. Per-request cost: just the encode pass.

The submission's text input is constructed to match the catalog indexing format:

```python
claims_str = " ".join(claims) if claims else ""
text = f"{name} {brand} {category} {claims_str}".strip()
```

Note: claims substitute for ingredients here. Supplier submissions typically don't include ingredient lists, but they always include claims ("Organic", "Plant-Based", etc.). Treating claims as the textual signal at the same position keeps the query vector roughly in the same region of CLIP space as the indexed catalog vectors.

The image + text combine into a single 512-dim unit vector using the same `(img_emb + txt_emb) / 2` average as Phase 0.

### 4.2 Cross-category k-NN search

**Module:** `backend/tools/opensearch_client.py:search_all_products()`

The system always runs an **unfiltered** k-NN with `k=20`. It does NOT filter by user-provided category at query time. Two reasons:

1. **Category-disagreement signal.** If a user submits a product as "Trail Mix" but the top 20 matches are all in "Protein Bars", the system needs to know. Filtering would hide this signal.
2. **Auto-detect mode.** When the user selects "Auto-detect", category is determined *from* the search results, not provided as input.

The query:

```json
{
  "size": 20,
  "query": {
    "knn": {
      "embedding": {
        "vector": [...512 floats...],
        "k": 20
      }
    }
  },
  "_source": ["sku", "name", "brand", "category", "price",
              "image_path", "claims", "ingredients"]
}
```

Each hit has `_score ∈ [0, 1]` (cosine similarity, sorted descending). The orchestrator stores all 20 hits as `all_similar_products` and then groups them by category for downstream analysis.

### 4.3 Category auto-detection

**Function:** `data_collector.py:infer_category()`

When the user explicitly chooses a category that exists in the catalog (not "Auto-detect", not "Other"), the system honors it. Otherwise it infers the category from the search results.

Algorithm:

1. Look at `category_groups` — the 20 hits grouped by their `category` field, sorted by max similarity descending.
2. Compute `global_max = max(similarity across all 20 hits)`.
3. **If `global_max < MIN_CATEGORY_SIMILARITY` (0.86):** Nothing in the catalog is close enough. Return `"New Category (nearest: {best_match_category})"` and flag `is_new_category=True`. This is a *genuinely* novel product type.
4. **Otherwise** do a similarity-weighted vote: for each category whose `max_similarity >= 0.86`, sum the similarity scores of its products. Pick the highest. This handles cases where the absolute best match is, say, in "Trail Mix" by chance but five "Protein Bars" sit just below it — the weighted vote correctly picks Protein Bars.

The threshold `0.86` is hand-tuned. Below it, CLIP matches start being unreliable for retail categorization (e.g. a packaged trail mix can score 0.84 against a wrapped granola bar simply because both are rectangular brown packaging).

### 4.4 Overlap classification

**Function:** `data_collector.py:classify_overlap()`

Run only on the **primary** category products (the inferred category's hits, not all 20). Three buckets:

- **High Overlap** — max similarity in the primary category > 0.88
- **Moderate Overlap** — max similarity 0.82–0.88
- **White Space** — max similarity < 0.82, *or* `is_new_category=True`

The thresholds are calibrated empirically against the demo catalog. At 0.88+, the matches are visually nearly identical products from different brands (RXBAR Blueberry vs. Clif Whey Blueberry). At 0.82–0.88, the matches share format and category but differ on flavor or ingredient. Below 0.82, the matches are loose category siblings, not direct competitors.

### 4.5 Enrich with sales, vendor, and benchmark data

**Module:** `backend/tools/database_client.py`

For every SKU in `all_similar_products` (up to 20), the system joins:

- **`sales_performance`** by SKU → `annual_revenue, weekly_units, velocity_rank, yoy_growth, stores_carrying, trend`
- **`products`** by SKU → `price, cost, margin_pct, status, shelf_position`
- **`vendor_scorecard`** by brand (the product's brand) → `fill_rate, otif_score, compliance_rating, relationship_tier`

Plus two scalar lookups:

- **`category_benchmarks`** for the inferred category → `market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend`
- **`vendor_scorecard`** for the *submitter's* brand → same scorecard fields

Plus a list lookup:

- **`category_benchmarks`** for every *adjacent* category found in the results (categories other than the inferred one). Useful for white-space products where the agent needs to triangulate from related categories.

The output is `enriched_products: list[dict]` — one row per similar SKU with every relevant field merged. This is what the agents read.

### 4.6 Category saturation

```python
category_saturation = {
    "total_skus_in_category": category_sku_count,
    "similar_products_found": len(primary_enriched),
    "category_is_full": category_sku_count >= 15,
}
```

The `category_is_full` flag is a key input to the verdict matrix. "Full" means the retailer is already carrying 15 or more SKUs in this category — beyond which adding another likely cannibalizes existing assortment without growing the shelf.

The number 15 is the demo's heuristic; in production it should be category-specific (Cookies might be "full" at 25 SKUs, Protein Bars at 18).

---

## 5. Phase 2 — Deterministic Verdict Engine

**Function:** `backend/pipeline/orchestrator.py:compute_verdict()`

Runs **before** the CrewAI agents start. Inputs: overlap classification + category saturation + is-new-category flag. Output: `(verdict, confidence)`.

| Overlap                | Category Full (≥15 SKUs) | Category Has Room (<15 SKUs) |
|------------------------|--------------------------|------------------------------|
| **High Overlap** (>0.88)     | DECLINE   (90%)       | MODIFY    (75%)              |
| **Moderate Overlap** (0.82–0.88) | MODIFY    (72%)       | AUTHORIZE (80%)              |
| **White Space** (<0.82)      | AUTHORIZE (85%)       | AUTHORIZE (85%)              |
| **New Category**             | AUTHORIZE (82%)       | AUTHORIZE (82%)              |

Pseudo-Python:

```python
if is_new_category:                return ("AUTHORIZE", 82)
if overlap == "White Space":       return ("AUTHORIZE", 85)
if overlap == "High Overlap":      return ("DECLINE", 90) if is_full else ("MODIFY", 75)
if overlap == "Moderate Overlap":  return ("MODIFY", 72) if is_full else ("AUTHORIZE", 80)
return ("AUTHORIZE", 70)  # fallthrough
```

The verdict is then injected into the DataPackage:

```python
raw_data["predetermined_verdict"] = predetermined_verdict
raw_data["predetermined_confidence"] = predetermined_confidence
```

Agent 3's task description reads these fields and is instructed: *"You do NOT decide the verdict. The verdict above is final."*

**Why deterministic?** Auditable, explainable, deterministic across runs, debuggable by category buyers. The LLM is creative; rules engines are predictable. Each side does what it's good at.

---

## 6. Phase 3 — Agentic Reasoning (CrewAI)

**Modules:** `backend/crew/agents.py`, `backend/crew/tasks.py`, `backend/crew/crew.py`

Three sequential agents. Each agent has `tools=[]` (no function-calling). Each agent receives the relevant subset of the DataPackage formatted into its task description as plain text. Each agent emits structured output in a strict `LABEL: value` format that the orchestrator can parse with regex.

The Crew is wired in `crew.py`:

```python
agent1 = risk_market_analyst()
agent2 = financial_modeler()
agent3 = recommendation_synthesizer()

task1 = risk_market_task(agent1, data_package)
task2 = financial_task(agent2, data_package, context=[task1])
task3 = recommendation_task(agent3, data_package, context=[task1, task2])

return Crew(
    agents=[agent1, agent2, agent3],
    tasks=[task1, task2, task3],
    process=Process.sequential,
    task_callback=task_callback,
)
```

`Process.sequential` means tasks run in order. The `context=[task1]` on task2 passes task1's output text into task2's prompt. CrewAI handles the prompt construction; we provide the data.

**LLM:** resolved by `backend/tools/llm_config.py`. On Cloudera AI (`LLM_PROVIDER=caii`) the agents call an open-weight model served by Cloudera AI Inference through its OpenAI-compatible API (validated with Llama 3.1 8B Instruct); on a laptop (`LLM_PROVIDER=openai`) they call OpenAI GPT-4o-mini. CrewAI's `LLM` wrapper is given the base URL, model id and bearer token explicitly.

### 6.1 Agent 1: Risk & Market Analyst

**Role:** Category performance and market strategy analyst.

**Goal:** Assess cannibalization risk and evaluate market context for the proposed product.

**Backstory:** An experienced category analyst and market strategist with deep expertise in grocery retail. Evaluates new items against existing shelf performance, understands velocity trends, competitive dynamics, and consumer behavior shifts.

**Input context (formatted in the task description):**

- Submission (name, description, price, category, claims, brand)
- Overlap classification
- Enriched competing products — per SKU: name, brand, category, similarity score, claims, annual revenue, weekly units, velocity rank, YoY growth, trend, status, price, margin, shelf position, vendor fill rate, vendor OTIF, vendor tier
- Competing vendors summary — by brand: how many SKUs, combined revenue, fill rate, OTIF
- Category benchmarks for the inferred category
- For White Space submissions: adjacent category benchmarks and the category-groups summary instead of competing products

**Behavior depends on overlap classification.** Two task templates:

- **White Space path** — task tells the agent there's NO direct cannibalization; reason about market opportunity, demand signals, nearest adjacent categories, and net category impact.
- **Overlap path (High or Moderate)** — task tells the agent to do per-SKU cannibalization analysis, flag underperformers as replacement candidates, compute projected decline of replaced products, and assess vendor relationship risk.

**Critical calculation in the overlap path:** the replacement scenario math.

```
For each replacement candidate:
    projected_annual_decline = current_revenue × abs(yoy_growth)
                                if yoy_growth < 0 else 0

New product Y1 revenue estimate:
    median_comparable_weekly_units × proposed_price × 52 × 0.75
    (the 0.75 = 25% knock-down for new-entry drag)

Net incremental impact:
    new_product_revenue − projected_decline
```

The task description explicitly cautions: *"Do NOT use the full revenue of replaced products as 'revenue lost'. The replaced products' customers don't vanish — most migrate to the new product or other category items. Only the PROJECTED DECLINE amount represents true category erosion."*

**Output format (overlap path):**
```
REASONING: <2 sentences in plain prose, one number + one SKU reference>
RISK_RATING: LOW | MEDIUM | HIGH
CANNIBALIZATION_DETAILS: <one bullet per competing product>
UNDERPERFORMERS: <bullets or NONE>
REPLACEMENT_CANDIDATES: <bullets or NONE>
REPLACEMENT_PROJECTED_DECLINE: $X annual
REPLACEMENT_NEW_PRODUCT_REVENUE: $X annual
REPLACEMENT_NET_INCREMENTAL: ±$X annual
VENDOR_RISKS: <bullets or NONE>
NET_CATEGORY_IMPACT: ±$X annual
CATEGORY: <name>
CATEGORY_GROWTH: X%
MARKET_TIMING: Early | On-Trend | Late
TOP_TREND: <description>
```

**Output format (white-space path):** Same fields, but with `CANNIBALIZATION_DETAILS: NONE`, `REPLACEMENT_CANDIDATES: NONE`, plus `OPPORTUNITY_TYPE` (New Category / Category Extension / Niche Play), `MARKET_OPPORTUNITY`, `NEAREST_CATEGORIES`, `DEMAND_SIGNALS`.

The agent does NOT do web research. The task description does not include any "search the web" instruction. All market context comes from the DuckDB `category_benchmarks` table.

### 6.2 Agent 2: Financial Modeler

**Role:** Retail financial analyst.

**Goal:** Project Year 1 financial performance and net category impact.

**Backstory:** A retail financial analyst who builds P&L projections for new product introductions. Models revenue, margin, and cannibalization impact using comparable product performance data. Always presents best, expected, and worst case scenarios.

**Input context:**

- Everything Agent 1 had
- Agent 1's full output (via `context=[task1]`)
- The submitter's vendor scorecard
- Adjacent category benchmarks (for white space)

**Computation logic the agent is instructed to follow:**

1. **Velocity estimate.** Pick a weekly units number anchored to comparable products' velocity. Adjust down 20–30% for new-entry drag. For white space, use adjacent categories and adjust down 30–50%.
2. **Expected revenue** = `weekly_units × proposed_price × 52`. All annual.
3. **Best case** = `Expected × 1.20`. **Worst case** = `Expected × 0.70`. The agent is told to ensure all three values are different numbers.
4. **Margin %** from the category average.
5. **Cannibalization breakdown.** For each rival SKU flagged by Agent 1, estimate dollar revenue impact (how much of that SKU's annual revenue shifts to the new product).
6. **Replacement scenario.** If Agent 1 named replacement candidates, sum their projected declines, compare against new product revenue, output net incremental category improvement.
7. **Vendor impact.** For each vendor whose products may be replaced, note relationship-tier risk.

**Output format:**
```
REASONING: <2 sentences>
WEEKLY_UNITS: X units/week
BEST_CASE: $X annual
EXPECTED: $X annual
WORST_CASE: $X annual
MARGIN: X%
CANNIBALIZATION_BREAKDOWN: <bullets>
CANNIBALIZATION_OFFSET: $X annual
NET_INCREMENTAL: $X annual
REPLACEMENT_SCENARIO: <bullets — declines + new revenue + net>
VENDOR_IMPACT: <bullets>
VENDOR_RELIABILITY: <sentence>
```

**Deterministic post-processing.** After the agent emits its output, `orchestrator.py:_fix_financial_scenarios()` parses out the `EXPECTED:` value and rewrites the `BEST_CASE:` and `WORST_CASE:` lines using the strict `1.20×` and `0.70×` multipliers. This guards against the common LLM failure mode where the model outputs three nearly identical numbers, or where Best is somehow smaller than Expected.

```python
expected_val = float(extract("EXPECTED", output))
best_val  = expected_val * 1.20
worst_val = expected_val * 0.70
output = re.sub(r"BEST_CASE:.*",  f"BEST_CASE: ${best_val:,.0f} annual revenue", output)
output = re.sub(r"EXPECTED:.*",   f"EXPECTED: ${expected_val:,.0f} annual revenue", output)
output = re.sub(r"WORST_CASE:.*", f"WORST_CASE: ${worst_val:,.0f} annual revenue", output)
```

### 6.3 Agent 3: Recommendation Synthesizer

**Role:** Senior category advisor and recommendation synthesizer.

**Goal:** Synthesize risk analysis and financial projections into a compelling recommendation report that explains the *predetermined* verdict.

**Backstory:** A senior category management executive with 20 years of experience in assortment decisions. Receives a predetermined verdict from the system's decision matrix and synthesizes evidence-based reasoning explaining why the verdict is correct.

**Input context:**

- Submission
- Overlap classification, category saturation
- Agent 1's output
- Agent 2's output
- **The predetermined verdict and confidence** (from `compute_verdict()`)

The task description explicitly tells the agent:

> YOUR ROLE: You do NOT decide the verdict. The verdict above is final and determined by the evaluation system's decision matrix based on overlap classification and category data. Your job is to synthesize the top 3 reasons that SUPPORT this verdict using evidence from the Risk & Market Analyst and Financial Modeler outputs.

Three branches of task template — one per verdict value (DECLINE / MODIFY / AUTHORIZE), each with verdict-appropriate action fields. For example, DECLINE produces `SUGGESTED_RETAIL: N/A`, `ROLLOUT: 0 stores`, plus a supplier-feedback section explaining what would change the answer.

**Output format (AUTHORIZE example):**
```
REASONING: <2 sentences synthesizing risk + financial into the verdict>
VERDICT: AUTHORIZE
CONFIDENCE: 80%
REASON_1: <evidence-based sentence>
REASON_2: <evidence-based sentence>
REASON_3: <evidence-based sentence>
SUGGESTED_RETAIL: $X.XX
PLACEMENT: <shelf placement>
ROLLOUT: X stores initially
REPLACE_SKUS: <SKU1 name>, <SKU2 name> or NONE
REPLACEMENT_NET_IMPACT: ±$X annual or N/A
```

For DECLINE the task includes a supplier-feedback paragraph; for MODIFY it specifies what conditions must change.

---

## 7. Phase 4 — Final Output Assembly

After the crew completes, `orchestrator.py:run_evaluation()` assembles the final output:

1. **Reassert verdict.** Always uses `raw_data["predetermined_verdict"]` and `raw_data["predetermined_confidence"]`. Even if Agent 3 hallucinated a different verdict in its output, the system overrides it.

2. **Extract Agent 3's fields.** `_extract_field()` regex-pulls REASON_1, REASON_2, REASON_3, SUGGESTED_RETAIL, PLACEMENT, ROLLOUT, REPLACE_SKUS, REPLACEMENT_NET_IMPACT.

3. **Fallback reasons.** If extraction fails (Agent 3 deviated from format), substitute canned reasons appropriate to the verdict:
   ```
   DECLINE: "The {category} already has {N} SKUs with {overlap}..."
   MODIFY:  "The product shows overlap with existing {category} items but..."
   AUTHORIZE: "The product fills a gap in the current assortment..."
   ```

4. **Verdict-specific overrides.** For DECLINE: force `SUGGESTED_RETAIL: N/A`, `ROLLOUT: 0 stores`, `REPLACE_SKUS: NONE`.

5. **Append supplier feedback.** For DECLINE and MODIFY, append a paragraph describing what would change the answer.

6. **Persist to evaluation_history.** Insert into DuckDB via `database_client.save_evaluation()`. Used by the History tab and `GET /api/evaluations/latest`.

7. **Emit final WebSocket message** with `phase: "done", step: 7, status: "done"`.

The final output is also returned synchronously from `run_evaluation()` as a dict for the HTTP path:

```python
{
    "data_package": raw_data,
    "result": final_output,         # the formatted string the UI parses
    "tasks_output": [task1_raw, task2_raw, task3_raw],
}
```

---

## 8. Real-Time WebSocket Protocol

**Endpoint:** `WS /ws/evaluation/{evaluation_id}`

The frontend opens this socket immediately after `POST /api/evaluate` returns an `evaluation_id`. The backend streams progress messages through it.

**Message envelope:**
```json
{
  "phase": "data_collection" | "reasoning" | "done",
  "step": 1..7,
  "step_name": "Visual Similarity Search",
  "agent": "Risk & Market Analyst",
  "status": "running" | "complete" | "done",
  "message": "Found 18 similar products. Highest similarity: 89%",
  "output": <stringified JSON or text>,
  "reasoning": "..."        // present on reasoning-step completes only
}
```

**Step-to-phase mapping:**

| Step | Phase            | Source                  | Speed       |
|------|------------------|-------------------------|-------------|
| 1    | data_collection  | Submission processing   | Instant     |
| 2    | data_collection  | OpenSearch k-NN         | 1–2 s       |
| 3    | data_collection  | DuckDB enrichment       | <1 s        |
| 4    | reasoning        | Agent 1 (Risk & Market) | 10–20 s     |
| 5    | reasoning        | Agent 2 (Financial)     | 10–20 s     |
| 6    | reasoning        | Agent 3 (Recommendation)| 10–15 s     |
| 7    | done             | Final assembly + persist| Instant     |

**`reasoning` field** is extracted by `orchestrator.extract_reasoning()`:

1. First try: regex-match the agent's `REASONING:` block (the first labeled field in every agent's `expected_output`).
2. Second try: take the leading prose before the first `FIELDNAME:` line.
3. Fallback: deterministic sentence synthesized from the DataPackage (e.g. `"I scanned 18 similar products in Protein Bars. The overlap reads as high overlap. That shapes where cannibalization risk sits."`).

The UI renders this as Newsreader-italic typewriter text in the Reasoner pane while the agent's structured output streams in below.

---

## 9. API Reference

All endpoints live in `backend/main.py`.

```
POST   /api/evaluate                          # { image_base64, name, description, price, category, claims, brand } → { evaluation_id }
WS     /ws/evaluation/{evaluation_id}         # Stream pipeline progress

POST   /api/evaluate/followup/{evaluation_id} # { question } → { followup_id }
WS     /ws/followup/{followup_id}             # Stream answer chunks: { status: "chunk", chunk: "..." } then { status: "done", output: "..." }

GET    /api/evaluations/latest                # { history, replay_available, result? } — powers empty-state replay strip
GET    /api/evaluations                       # All past evaluations from DuckDB evaluation_history
GET    /api/evaluations/stats                 # Aggregate stats (verdicts, avg confidence, total revenue projected)

POST   /api/evaluate/batch                    # Submit multiple products → { batch_id }
WS     /ws/batch/{batch_id}                   # Per-product progress

GET    /api/products/{sku}                    # Product details from OpenSearch by SKU
GET    /api/catalog/summary                   # Category counts + SKU stats
GET    /api/catalog/products                  # Full catalog listing with filters

GET    /api/images/{filename}                 # Serve product image from data/images/catalog/
```

**Follow-up:** `backend/pipeline/followup.py` reuses the cached DataPackage + prior task outputs from the original evaluation. The follow-up question is scoped (the user can ask about the same product but not start a new evaluation) and the answer streams via the openai SDK directly (no CrewAI involvement).

---

## 10. Frontend Architecture

`frontend/` is React + TypeScript + Vite + Tailwind v4. Single page app, proxies `/api` and `/ws` to backend:8001 via `vite.config.ts`.

**Tab structure** (`App.tsx` → `ReasonerHeader`):

- `evaluate` — main submission + workflow UI (default)
- `catalog` — catalog overview + category benchmarks
- `history` — past evaluations from DuckDB
- `merchant` — merchant queue view
- `supplier` — supplier-facing portal
- `batch` — batch evaluation

**Evaluate-tab layout** (`EvaluateShell`):

```
┌──────────────────────────────────────────────────────────────┐
│ ReasonerHeader (6 tabs, brand orange #EA580C accent)         │
├────────────────┬─────────────────────────────────────────────┤
│ AgentRail      │ Main thread:                                │
│   Risk Analyst │   • SubmissionPanel (or VerdictHero)        │
│   Financial    │   • WorkflowStepper                         │
│   Recommender  │   • ArtifactCard: Visual Similarity         │
│                │   • ArtifactCard: Risk & Market Analysis    │
│  states:       │   • ArtifactCard: Financial Projection      │
│   idle         │   • ArtifactCard: Shelf Planogram           │
│   running      │   • FollowupPrompt                          │
│   complete     │                                             │
└────────────────┴─────────────────────────────────────────────┘
```

**Key components:**

- `SubmissionPanel.tsx` — drag-and-drop image, form fields, base64-encodes and POSTs to `/api/evaluate`.
- `useEvaluationSocket.ts` — opens the WebSocket, accumulates messages into a state machine of step statuses. Also exposes `restoreFromResult()` for replay.
- `AgentRail.tsx` — three agent cards. Each transitions idle → running (shimmer + dot-pulse) → complete (✓ + elapsed time).
- `ArtifactCard.tsx` — collapsible header + body wrapper. Every output panel uses this.
- `ReasoningStream.tsx` — Newsreader-italic typewriter (~70 chars/sec) that types out the `reasoning` field on each agent-complete message.
- `VerdictHero.tsx` — 72px display-scale verdict word (`DECLINE.` / `AUTHORIZE.` / `MODIFY.`) + animated counter for confidence + amber rule sweep.
- `SimilarityGallery.tsx` — the wow moment. Submitted product on the left, top similar products on the right with similarity-percentage color bars.
- `CannibalizationTable.tsx` — per-SKU breakdown rendered inside `RiskAssessment`.
- `FinancialSummary.tsx` — Best/Expected/Worst with a replace-count scrubber (test impact of replacing 2 / 3 / 4 / 5 SKUs).
- `PlanogramView.tsx` — 4-zone shelf grid with the new product outlined.
- `FollowupPrompt.tsx` + `FollowupThread.tsx` + `useFollowupSocket.ts` — post-verdict Q&A.

**Real-time UX:**

- Steps 1–3 (deterministic) tick through almost instantly (~2–3 seconds total).
- The similarity gallery populates after step 2 — this is the wow moment.
- Steps 4–6 each take 10–20 seconds. The corresponding ArtifactCard runs a shimmer + dot-pulse animation until its agent completes; then the reasoning streams in italic, and the structured output renders.
- At step 7, the `VerdictHero` swaps in for the SubmissionPanel.

---

## 11. End-to-End Setup Guide

For an engineer setting this up from a fresh clone on macOS or Linux.

### Prerequisites

- Docker Desktop running
- Python 3.11+
- Node.js 18+
- ~3 GB free disk (for OpenSearch data, CLIP weights, product images)
- An OpenAI API key

### Step 1: Clone and configure

```bash
git clone git@github.com:neelabhpant/new-item-evaluation.git
cd new-item-evaluation
cp .env.example .env
# Edit .env: set OPENAI_API_KEY
```

### Step 2: Start OpenSearch

```bash
docker compose up -d
# Verify
curl http://localhost:9200
# Should return cluster info JSON
```

### Step 3: Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
# First time: torch will download CLIP weights to ~/.cache/clip (~150 MB)
```

### Step 4: Bootstrap the catalog (one-time, ~10–15 minutes)

```bash
# 4a. Download images and metadata from Open Food Facts (~5 min)
python scripts/download_catalog.py

# 4b. Assign categories to each product (~1 second)
python scripts/assign_categories.py

# 4c. Create the OpenSearch index with the knn_vector mapping
python scripts/create_index.py

# 4d. Generate CLIP embeddings and index every product (5–10 min on CPU)
python scripts/index_catalog.py

# 4e. Seed DuckDB with synthetic retail data (~1 second)
python backend/data/init_db.py
```

### Step 5: Verify bootstrap

```bash
# OpenSearch: should match indexing count
curl http://localhost:9200/product-catalog/_count

# DuckDB: should show ~4 tables, hundreds of rows
python -c "import duckdb; con=duckdb.connect('data/store.db'); \
  print(con.execute('SELECT COUNT(*) FROM products').fetchone()); \
  print(con.execute('SELECT COUNT(*) FROM sales_performance').fetchone()); \
  print(con.execute('SELECT COUNT(*) FROM category_benchmarks').fetchone()); \
  print(con.execute('SELECT COUNT(*) FROM vendor_scorecard').fetchone())"
```

### Step 6: Start the backend

```bash
cd backend && python -m uvicorn main:app --port 8001
# Should log: "INFO: Uvicorn running on http://0.0.0.0:8001"
# First request loads the CLIP model into memory (~5 seconds)
```

### Step 7: Start the frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
# Opens http://localhost:5173
```

### Step 8: Smoke test

```bash
# In a third terminal:
source venv/bin/activate
python backend/smoke_test.py
# Expect: 5/5 passing in ~90 seconds
```

### Step 9: Run a real submission

Open `http://localhost:5173`. On the Evaluate tab:

1. Drag a product image into the SubmissionPanel.
2. Fill in: name, description, price (e.g. $5.49), category (or "Auto-detect"), claims.
3. Click Submit.
4. Watch the workflow stepper tick through steps 1–3, then the three agent cards activate one by one.
5. After ~45 seconds: VerdictHero displays AUTHORIZE / MODIFY / DECLINE.

---

## 12. Architectural Decisions & FAQ

**Why CLIP ViT-B/32 and not a larger model?**
ViT-B/32 produces 512-dim vectors at low compute cost (~200 ms per image on CPU). ViT-L/14 would give better matches but at 4× the compute and 768-dim vectors that bloat the index. For retail catalog matching, the lift from a larger model is small relative to the cost.

**Why average image and text embeddings instead of concatenating?**
Averaging keeps the search space at 512-dim, ensures both modalities live in the same space (CLIP was trained for this), and makes query vectors directly comparable to indexed vectors. Concatenation would require maintaining separate query and index halves and tuning a weight between them.

**Why HNSW instead of brute-force k-NN?**
For 295 products, brute force is fine. The HNSW choice future-proofs the system for catalogs of 100K+ products without code changes. Recall stays >95% at default HNSW parameters.

**Why DuckDB instead of Postgres?**
Zero server, embedded, no Docker needed beyond OpenSearch, fast analytical queries. Perfect for a demo. Production would migrate to Postgres or Snowflake.

**Why CrewAI and not raw OpenAI tool-calling?**
CrewAI gives us the sequential-process scaffolding and context-passing between tasks for free. The agents could be replicated with raw OpenAI calls but CrewAI removes about 200 lines of prompt-plumbing code.

**Why no tools on the agents?**
Tool-calling adds 10–30 seconds per call and introduces hallucination risk on tool arguments. We collect all data upfront in 2–3 seconds and inject it as task-description text. Faster and more reliable.

**Why is the verdict deterministic?**
Buyers need auditable, reproducible decisions. An LLM "deciding" the verdict drifts across runs and is hard to defend in a category review. The matrix is explainable in one slide.

**Why GPT-4o-mini and not GPT-4o?**
Cost and latency. For structured-output reasoning over pre-collected data, 4o-mini is sufficient. Output quality is gated more by prompt engineering than model size.

**Why 86% as the new-category threshold?**
Empirical, calibrated against the demo catalog. Below 0.86, CLIP matches start to be unreliable for retail-category inference. Above 0.86, the matches are consistently in-category. Tune per catalog.

**Why force Best = Expected × 1.20 and Worst = Expected × 0.70 after the fact?**
LLMs frequently emit scenario values that are mathematically inconsistent (e.g. all three equal, or Worst > Expected). Post-processing guarantees the buyer sees a sensible scenario spread without re-prompting the agent.

**Why is `category_is_full = sku_count >= 15`?**
Demo heuristic. In production, this should be category-specific and informed by shelf-space data. The matrix logic is decoupled from the threshold — changing the cutoff doesn't require touching `compute_verdict()`.

**Can the system run fully offline?**
No. The OpenAI API is the only external dependency at evaluation time. Everything else (OpenSearch, DuckDB, CLIP model) runs locally. Catalog bootstrap requires internet access for Open Food Facts.

**How does follow-up Q&A work?**
`backend/pipeline/followup.py` looks up the cached DataPackage and the three task outputs from the original evaluation. It constructs a system prompt that includes all that context and the user's question, then streams completion deltas through the openai SDK directly. No CrewAI, no second pipeline run. Scoped: the LLM is instructed to answer only questions about *this product's evaluation*, not start a new analysis.


---

## 13. Cloudera AI Deployment

The full deployment guide is in [DEPLOY_CLOUDERA.md](DEPLOY_CLOUDERA.md). This section records the design decisions.

**One application, one origin.** Cloudera AI Workbench exposes a single port per Application (`CDSW_APP_PORT`), so `deploy/app.py` runs uvicorn with one worker and FastAPI serves `frontend/dist` (built by `deploy/build_frontend.sh`) together with `/api` and `/ws`. The frontend needed no change: all calls are relative and the WebSocket URL is derived from `window.location`. One worker is mandatory because evaluation state lives in in-process dictionaries.

**LLM provider abstraction (`backend/tools/llm_config.py`).** The two call sites (`crew/agents.py`, `pipeline/followup.py`) ask this module for a CrewAI `LLM` or an `openai.OpenAI` client. For `LLM_PROVIDER=caii` the model string stays `openai/<model>` (litellm's OpenAI-compatible adapter) with `base_url` pointing at the Cloudera AI Inference endpoint. The bearer token is resolved per call: `LLM_API_KEY` → `CDP_TOKEN` → the workload JWT at `/tmp/jwt` that Cloudera AI injects into every pod. Agents are rebuilt for each evaluation, so a refreshed token is picked up without a restart. Each task's `expected_output` now ends with an explicit "output only the labeled lines" rule, which is what keeps 7–8B instruction models inside the `LABEL: value` format the orchestrator parses. Reasoning-style models that print their chain of thought (e.g. Nemotron Super) break that parsing and are not used.

**OpenSearch modes (`backend/tools/opensearch_conn.py`).** URL, basic auth and TLS are configured in one place, so the client, `main.py` and the index scripts work against three deployments: docker-compose on a laptop, OpenSearch embedded in the Cloudera AI application pod (`deploy/opensearch/embedded.py`: official 2.11 bundle, bundled JDK and k-NN plugin, security plugin disabled, bound to 127.0.0.1), or a Cloudera Data Hub cluster behind Knox. Index data for the embedded mode is kept on pod-local disk (Lucene lock files do not tolerate NFS) and rebuilt at start from `data/catalog_embeddings.jsonl`, the cache written by `scripts/index_catalog.py --embed-only`. Documents are loaded with the `_bulk` API. Engine, space type and thresholds are unchanged, so verdicts match the laptop.

**Iceberg via Impala (`backend/tools/db.py`).** `DB_BACKEND=impala` routes all SQL in `database_client.py` through `impyla` to a Cloudera Data Warehouse (or Data Hub) Impala endpoint using the workload user and password. `backend/data/init_db.py --backend impala` creates `new_item_eval.*` as `STORED BY ICEBERG` tables and seeds them with the same `Random(42)` data as the DuckDB file; `evaluation_history` is an Iceberg table too, so the History tab is backed by the lakehouse. The only dialect differences handled are placeholders (`%s` vs `?`), the reserved word `timestamp` (quoted per backend) and the absence of column defaults on Iceberg (`now()` is written explicitly).

**Bootstrap as Workbench Jobs (`deploy/cml_setup.py`).** Four chained jobs install dependencies (CPU torch wheel, CLIP weights, OpenSearch bundle, Node + frontend build), download the 295 images referenced by the committed `data/catalog_products.json` (`scripts/fetch_images.py`, reproducible unlike the search-API based `download_catalog.py`), compute embeddings, and create the Iceberg tables. Packages live in `~/.local` on project storage and are shared with the Application, which is why jobs and application are pinned to the same Python runtime.

**Verification.** `GET /api/health` reports every dependency; `deploy/check_endpoints.py` tests the AI Inference endpoint (chat + streaming), OpenSearch (health + k-NN plugin) and Impala; `backend/smoke_test.py` takes `API_BASE` so it can run against `deploy/app.py` inside a session.
