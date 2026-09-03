# Catalog row: Applied AI - Blueprint Catalog

Sheet: `Cloudera Blueprint Catalog`, one row per blueprint, columns B through R. Columns D, F, G, H, I and Q are dropdown-validated; every value below is taken from the sheet's own validation lists. Tags are semicolon separated as in the existing rows.

## Values by column

| Column | Header | Value |
| --- | --- | --- |
| B | Blueprint Use Case | Multimodal New Item Evaluation for Retail |
| C | One Sentence Executive Summary of Blueprint | This blueprint evaluates supplier new product submissions against a retailer's existing assortment on Cloudera AI: CLIP image and text embeddings with OpenSearch k-NN find look-alike products, Iceberg tables in Cloudera Data Warehouse supply sales and vendor data, and three CrewAI agents on an open-weight Llama or Qwen model served by Cloudera AI Inference write the risk, financial and recommendation analysis behind a deterministic AUTHORIZE / MODIFY / DECLINE verdict. |
| D | Catalog Classification | Enterprise Blueprint, Launchable (AMP) |
| E | Industry Alignment | TRUE |
| F | Industry Focus | Retail |
| G | Cloudera Products Used | Workbench, Inference Service, Data Warehouse |
| H | Source / Partner | Internal |
| I | Cloudera Alignment | High |
| J | Public Github link | https://github.com/neelabhpant/new-item-evaluation |
| K | Working / Private Github link | https://github.com/neelabhpant/new-item-evaluation |
| L | Maintainer name | Neelabh Pant |
| M | Reprise/Demo Assets | NOT YET PROVIDED |
| N | Tags | Retail; CPG; Assortment Planning; New Item Evaluation; Cannibalization; Multimodal; CLIP; Vector Search; OpenSearch; k-NN; Agentic AI; CrewAI; Iceberg; Impala; Open-Weight LLM; Llama; Qwen; CAI; AMP |
| O | License Scan JIRA | (blank; Apache 2.0 code, Open Food Facts data under ODbL) |
| P | Reviewed / Action Needed | Multimodal New Item Evaluation for Retail - Blueprint Comments |
| Q | Status | Ready for Review |
| R | Customers Interested | (blank) |

## Paste line

Tab separated, columns B through R in order. Paste into cell B of the next empty row; blank cells are preserved as empty tabs.

```
Multimodal New Item Evaluation for Retail	This blueprint evaluates supplier new product submissions against a retailer's existing assortment on Cloudera AI: CLIP image and text embeddings with OpenSearch k-NN find look-alike products, Iceberg tables in Cloudera Data Warehouse supply sales and vendor data, and three CrewAI agents on an open-weight Llama or Qwen model served by Cloudera AI Inference write the risk, financial and recommendation analysis behind a deterministic AUTHORIZE / MODIFY / DECLINE verdict.	Enterprise Blueprint, Launchable (AMP)	TRUE	Retail	Workbench, Inference Service, Data Warehouse	Internal	High	https://github.com/neelabhpant/new-item-evaluation	https://github.com/neelabhpant/new-item-evaluation	Neelabh Pant	NOT YET PROVIDED	Retail; CPG; Assortment Planning; New Item Evaluation; Cannibalization; Multimodal; CLIP; Vector Search; OpenSearch; k-NN; Agentic AI; CrewAI; Iceberg; Impala; Open-Weight LLM; Llama; Qwen; CAI; AMP		Multimodal New Item Evaluation for Retail - Blueprint Comments	Ready for Review	
```

## Notes for the reviewer

- OpenSearch is not a Cloudera service. It runs as an embedded single-node process inside the Workbench Application pod and is listed in Tags, not in Cloudera Products Used.
- The repository must be public for the AMP launch; the maintainer is flipping `neelabhpant/new-item-evaluation` to public. Until then column J can be set to NOT YET PROVIDED.
- No Reprise has been recorded. Column M stays NOT YET PROVIDED until one exists.
