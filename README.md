Product Documentation

## Product Overview

**Product name: Singapore Tourism RAG + Controlled Agent**

This product helps visitors ask natural-language questions about Singapore attractions, visitor rules, opening hours, ticketing, accessibility, and transportation. It uses retrieval-augmented generation (RAG) over frozen official website snapshots, then calls live official information tools when needed. Answers include source links and evidence dates.

The current product is a prototype running in Google Colab. This document is based on `pe6201_singapore_tourism_agent_colab.py` and two supplied baseline experiment archives. Prompts inside the source file are treated as product configuration to analyze. Although the source introduction mentions a Gradio demonstration link, the supplied code does not contain a verifiable Gradio interface implementation. The implemented entry point documented here is `ask_agent(question)`.

## 1. Persona: Target Users

| User group | Needs and usage scenarios | Product value |
| --- | --- | --- |
| First-time independent visitors to Singapore (primary users) | Unfamiliar with attractions and transportation; need to confirm how to get there, when to visit, and applicable restrictions | Direct answers drawn from official information reduce time spent searching multiple websites |
| Chinese- or English-speaking visitors | Want to ask tourism questions in their preferred language and understand official information | Responses follow the question's language; bilingual output is provided only when requested |
| Visitors traveling with children, older adults, or people with accessibility needs | Need to verify facilities, walking or shuttle arrangements, and visitor rules | Retrieves information relevant to stated constraints and identifies details that cannot be confirmed |
| Visitors making time-sensitive plans | Need current opening hours, prices, or temporary closure information | Reads or searches current official information and states the verification date |

**Example user story:** As a first-time visitor traveling with an older family member, I want to ask in Chinese how to reach an attraction, whether accessible facilities are available, and what its current opening hours are, so that I can plan using verifiable official information.

These personas are inferred from the product's functionality; no real user research results have been supplied. The product provides tourism information assistance. It does not purchase tickets, make payments, or book reservations. Its route tool provides official transportation guidance rather than live navigation.

## 2. Input: What the System Receives

### 2.1 User Input

The asynchronous function `await ask_agent(question)` receives a non-empty natural-language question. Questions may include an attraction, destination, origin, date or time, and travel constraints. Examples include:

- “How can I get to Singapore Zoo from the city center?”
- “What are this attraction's current opening hours? Please provide official sources.”
- “Which facilities and visitor rules should I confirm when visiting with a wheelchair user?”

Each call currently receives one question string. Chat history, location coordinates, images, and audio are not explicitly passed into the function. Chinese and English are intended usage languages, but multilingual quality still requires measurement.

### 2.2 Knowledge and Configuration Inputs

| Input | Content and purpose |
| --- | --- |
| `urls.xlsx` | Official webpage inventory with standard columns `title`, `url`, `organisation`, and `topic`; used to collect the corpus |
| Official HTML and PDF documents | Text is extracted and saved as frozen snapshots to provide traceable factual evidence |
| Configuration and credentials | `OPENROUTER_API_KEY` in Colab Secrets, model configuration, retrieval parameters, and an official-domain allowlist |
| Evaluation question set | `evaluation_questions_30.xlsx`, containing questions, reference answers or rubrics, expected sources, expected tools, and abstention requirements |
| Human review file | Completed `human_review_10_with_disagreements.xlsx`, used to summarize human scores and disagreements with the automated judge |

The project maintainer supplies the webpage inventory. The code builds its allowlist from included corpus domains and additional configuration, so source trust also depends on the maintainer verifying those websites.

## 3. Output: What the System Produces

### 3.1 User-Facing Output

The system produces a natural-language answer intended to include:

1. A direct response to the question, such as visitor rules, facility information, or transportation options.
2. Recommendations relevant to the user's constraints, distinguished from verified facts.
3. Explicit labels for snapshot evidence and live verification results, with corresponding dates.
4. A final Sources section listing the complete official URLs used.
5. An explanation of the search performed, missing evidence, and uncertainty when retrieval and live queries cannot verify the answer.

These are requirements specified in the Agent instructions, rather than guarantees that every run satisfies them. Actual quality is assessed through validation, automated evaluation, and human review.

### 3.2 Developer and Evaluation Output

`ask_agent()` returns the following structure:

```text
{
  question: the user's question,
  answer: the final response,
  validation: source, date, and tool-use checks,
  audit: the tool-call audit log for this question,
  elapsed_seconds: end-to-end request duration
}
```

The project also generates `corpus_manifest.csv`, `snapshots/`, `chunks.csv`, `faiss.index`, `evaluation_results_agent.csv/.xlsx`, and human review files. Experiment exports include automated and human evaluation summaries, judge–human disagreement summaries, tool logs, and configuration metadata for review and reproduction.

## 4. High-Level Product Architecture

### 4.1 Box Diagram

```text
Knowledge Base Construction
+------------------------------------------+
| urls.xlsx: official webpage inventory    |
+--------------------+---------------------+
                     v
+------------------------------------------+
| Fetch HTML/PDF and extract text           |
| Save dates, sources, and file hashes      |
+--------------------+---------------------+
                     v
+------------------------------------------+
| Corpus quality checks and text chunking  |
| Local multilingual embeddings            |
+--------------------+---------------------+
                     v
+------------------------------------------+
| Frozen snapshots + chunks + FAISS index  |
+------------------------------------------+
                     ^
                     | queried by retrieval tools

Online Question Answering
+------------------------------------------+
| User question: attraction/time/constraints|
+--------------------+---------------------+
                     v
+-----------------------------------+   +--------------------------------+
| ask_agent / Agents SDK            |<->| External LLM via OpenRouter    |
| Business rules, scheduling, audit |   | Tool selection, evidence       |
|                                   |   | interpretation, answer drafting|
+--------------------+--------------+   +--------------------------------+
                     | tool requests down / evidence back up
                     v
+------------------------------------------------------------------------+
| Tools                                                                  |
| 1. search_knowledge_base     -> Local FAISS and official snapshots       |
| 2. get_route_information     -> Snapshot transport and route information |
| 3. fetch_live_official_page  -> Current content of a known official URL   |
| 4. search_live_official_web  -> OpenRouter web search / Exa               |
|                                Restricted to allowed official domains  |
+-----------------------------------+------------------------------------+
                                    | evidence synthesized by Agent/LLM
                                    v
+------------------------------------------------------------------------+
| Final answer -> validate_agent_answer -> Return structured result       |
| Answer + official sources + evidence dates + validation + audit log     |
+-----------------------------------+------------------------------------+
                                    v
+------------------------------------------------------------------------+
| Evaluation: question set -> tool matching / validator / LLM judge       |
|             -> human review                                            |
+------------------------------------------------------------------------+
```

### 4.2 How Inputs Become Outputs

**Offline construction:** The system cleans and deduplicates the webpage inventory, then collects page content. Pages with collection errors or fewer than 100 text characters are classified as failed. Pages with 100–299 characters require manual review; pages with at least 300 characters are automatically included. Accepted text is split into chunks of up to 450 tokens with an 80-token overlap. `paraphrase-multilingual-MiniLM-L12-v2` produces normalized vectors stored in a FAISS inner-product index.

**Online business logic:** Agent instructions require `search_knowledge_base` first, followed by an assessment of whether the evidence directly answers the question. When a relevant official URL is available and information may have changed, the Agent calls `fetch_live_official_page`. If the snapshot cannot directly answer the question, it calls `search_live_official_web`. Transportation questions also require `get_route_information`. General knowledge retrieval returns six evidence passages by default.

**External LLM:** Through OpenRouter, the model receives the question, product rules, and tool results to select tools and generate the answer. The supplied source configures `openai/gpt-6.1-sol-pro`; this is the configuration identifier recorded in the code, and current service availability was not independently checked. The live search tool also invokes an external model and search service. Factual claims should be grounded in tool evidence.

**Output validation:** The validator checks whether local retrieval was used, source URLs are present, all URLs belong to allowed domains, and a date in `YYYY-MM-DD` format appears. Validation results are returned with the answer. The current implementation does not automatically block or regenerate an answer after validation fails.

### 4.3 Current Implementation Limitations

- The retrieval-first workflow is mainly guided by LLM instructions. The validator checks whether local retrieval occurred, but does not verify tool-call order.
- `MIN_SIMILARITY = 0.25` is configured, but `retrieve()` does not filter results using that threshold. Automatic abstention based on low similarity is therefore not implemented.
- The route tool retrieves snapshot information and does not connect to live maps, traffic, or timetable APIs.
- The validator does not establish whether source content supports every factual claim or whether every cited URL was actually returned by a tool. These require further verification.
- In the supplied source, the automated judge uses the same model configuration as answer generation. It receives the question, reference rubric, expected source, and candidate answer, rather than complete tool evidence. Judge scores should therefore be interpreted alongside human review.

## 5. Metrics Targeted

**The values below are proposed acceptance targets for this documentation. The source code does not specify established target thresholds, and there is no evidence that these targets were registered before the historical experiments.** Future evaluations should fix the question set, snapshot, model, and scoring rules before testing.

The evaluation design uses 30 manually designed questions and human review of 10 specified questions. The actual question set contains eight time-sensitive questions, six visitor-rule questions, six route/accessibility questions, four multi-source itinerary questions, three ambiguous/adversarial questions, and three unanswerable questions.

| Metric | Definition / code field | Proposed target |
| --- | --- | --- |
| Tool selection accuracy | Expected tools must be a subset of actual tools; order is ignored and additional tools are permitted; `tool_selection_correct` | ≥90%; at least 27/30 |
| Basic validation pass rate | Local retrieval used, source URL present, all URLs allowlisted, and evidence date present; `validator_passed` | 100%; 30/30 |
| Evidence faithfulness | No fabricated or unsupported factual claims; `judge_faithful` | ≥90%; at least 27/30 |
| Snapshot correctness | Correctness against reference answers or evaluation rubrics; `judge_snapshot_correct` | ≥90%; at least 27/30 |
| Citation support | Official sources reasonably support the main factual claims; `judge_citation_support` | ≥90%; at least 27/30 |
| Appropriate uncertainty | Missing, conflicting, or outdated evidence is handled appropriately; `judge_uncertainty` | ≥90%; at least 27/30 |
| User constraint satisfaction | Important question requirements are satisfied; `judge_constraint_satisfaction` | ≥90%; at least 27/30 |
| Human overall pass rate | Overall human assessment; `human_overall_pass` | ≥90%; at least 9/10 |
| Judge–human disagreement rate | Different scores divided by valid paired scores for each dimension | ≤10% per dimension; at most 1/10 |

**Reporting rules:** Each metric must report passed questions, valid scores, and percentage, together with valid-score coverage, request failures, and missing judge scores. The code excludes missing scores from summaries, so a high rate among remaining valid scores alone does not establish success across all 30 questions. Time-sensitive answers should be evaluated against live evidence, with differences from older snapshots explained.

Response latency, API cost, and user usability are future monitoring metrics. Evidence-based targets have not yet been defined. End-to-end duration distributions, per-question costs, and real user feedback should be collected before setting performance and experience targets.

## 6. Metrics Reached

### 6.1 Experiment Evidence and Measurement Rules

Measured results come from two supplied experiment archives:

- `gpt6_1_baseline_20261004_144053.zip`: model identifier `openai/gpt-6.1-sol-pro`; experiment export time **2026-10-04 22:40:53 (Asia/Shanghai)**.
- `gpt4o_mini_baseline_20261004_122103.zip`: model identifier `openai/gpt-4o-mini`; experiment export time **2026-10-04 20:21:03 (Asia/Shanghai)**.

These times are converted from UTC timestamps in `baseline_metadata.json`. They are export timestamps, not test durations. Both experiments record 30 evaluation questions and a snapshot date of 2026-10-04. The embedding model, Top-K=6, temperature configuration, and four-tool list match. Question IDs and question text match across the result files, as do the exported Agent instructions. However, complete corpus and execution-environment evidence was not included, so full experimental control cannot be established.

The automated results below use `evaluation_results_*_corrected.csv`. Each metric was recounted and checked against `automatic_summary_*.csv`. Tool scoring uses the expected-subset-of-actual rule. All seven automated metrics have 30 valid scores in both experiments, and both result files contain zero non-empty `evaluation_error` entries. This does not imply that every tool call succeeded or every answer was correct.

### 6.2 Automated Evaluation Results: 30 Questions per Model

| Metric | Proposed target | GPT-6.1 result | GPT-4o-mini result | GPT-6.1 vs. target |
| --- | --- | --- | --- | --- |
| Tool selection accuracy | ≥90% | **27/30 (90.0%)** | 14/30 (46.7%) | Met |
| Basic validation pass rate | 100% | **4/30 (13.3%)** | 13/30 (43.3%) | Not met |
| Evidence faithfulness (judge) | ≥90% | 7/30 (23.3%) | 20/30 (66.7%) | Not met |
| Snapshot correctness (judge) | ≥90% | 20/30 (66.7%) | 13/30 (43.3%) | Not met |
| Citation support (judge) | ≥90% | 18/30 (60.0%) | 25/30 (83.3%) | Not met |
| Appropriate uncertainty (judge) | ≥90% | 16/30 (53.3%) | 14/30 (46.7%) | Not met |
| User constraint satisfaction (judge) | ≥90% | 19/30 (63.3%) | 20/30 (66.7%) | Not met |

Compared with GPT-4o-mini, GPT-6.1 improved tool selection accuracy by **43.3 percentage points**, snapshot correctness by **23.3 percentage points**, and appropriate uncertainty by **6.7 percentage points**. Its basic validation, judge faithfulness, citation support, and constraint satisfaction scores were lower. The results therefore do not show improvement across every metric.

### 6.3 Human Review Results: 10 Specified Questions

The reviewed questions are Q01, Q06, Q09, Q13, Q15, Q19, Q21, Q24, Q25, and Q29. GPT-6.1 results come from `human_review_10_gpt6_1.csv` and `human_summary_gpt6_1.csv`. GPT-4o-mini results come from `human_summary_gpt4o_mini.csv`; its archive also contains the human review XLSX file.

| Human evaluation metric | GPT-6.1 | GPT-4o-mini |
| --- | --- | --- |
| Tool selection accuracy | 10/10 (100.0%) | 4/10 (40.0%) |
| Evidence faithfulness | 8/10 (80.0%) | 3/10 (30.0%) |
| Snapshot correctness | 8/10 (80.0%) | **3/9 (33.3%)** |
| Citation support | 9/10 (90.0%) | 2/10 (20.0%) |
| Appropriate uncertainty | 9/10 (90.0%) | 5/10 (50.0%) |
| User constraint satisfaction | 7/10 (70.0%) | 4/10 (40.0%) |
| **Human overall pass rate** | **8/10 (80.0%)** | **3/10 (30.0%)** |

GPT-6.1 improved the human overall pass rate by **50 percentage points** on this reviewed sample, but did not reach the proposed 90% overall target. Its human citation support and uncertainty scores reached 90%. These 10 selected questions cannot directly represent performance across all 30 questions or real users.

**Denominator difference:** GPT-4o-mini metadata states that Q06's reference answer was unrelated to the question, so human snapshot correctness was marked N/A. Valid-score coverage for that metric is 9/10 (90%). GPT-6.1's Q06 review also identifies a mismatched reference snapshot, but the reviewer considered its answer relevant to Mandai / Singapore Zoo promotions and assigned a snapshot correctness score of 1. The 80.0% versus 33.3% comparison therefore includes a difference in how that evaluation issue was handled.

### 6.4 GPT-6.1 Judge–Human Disagreement

Disagreement is calculated from judge and human scores for the same question and dimension. It is not calculated by subtracting the full 30-question judge rate from the 10-question human rate.

| Evaluation dimension | Disagreements / valid pairs | Disagreement rate | Against proposed target ≤10% |
| --- | --- | --- | --- |
| Evidence faithfulness | 6/10 | **60.0%** | Not met |
| Snapshot correctness | 2/10 | 20.0% | Not met |
| Citation support | 2/10 | 20.0% | Not met |
| Appropriate uncertainty | 2/10 | 20.0% | Not met |
| User constraint satisfaction | 1/10 | 10.0% | Met |

Source: `judge_human_comparison_gpt6_1.csv`. The GPT-4o-mini archive does not include a corresponding disagreement summary, so an uncomputed disagreement rate is not reported here. GPT-6.1's substantial faithfulness disagreement indicates that the automated evaluation needs calibration. Neither scoring method alone establishes factual quality.

### 6.5 Interpretation and Improvement Priorities

**Observed product performance:** GPT-6.1 selected the expected tools more often in the 30-question evaluation and achieved a higher overall pass rate in the specified human sample. These results support further development of its tool orchestration and source-grounded answers.

**Main unmet requirement:** GPT-6.1 passed basic validation on only 4/30 questions. This metric requires local retrieval, source URLs, allowed domains, and a date simultaneously. The exported result CSV does not preserve individual validation checks, so the failures cannot all be attributed to missing dates or citations. Future runs should save complete per-question `validation` results, identify failed checks, and add output-format checks and a repair step after failure.

**Evaluation quality:** The human records identify mismatched reference data for Q06, while faithfulness has a 60% paired disagreement rate. The next evaluation should correct question–reference mappings, provide actual tool evidence to the judge, and standardize N/A handling before retesting. Historical results should remain recorded as observed.

**Missing product measurements:** The archives do not provide sufficient measurements to report average response latency, P95 latency, average API cost, real user satisfaction, or corpus inclusion rate. GPT-6.1 metadata explicitly marks average latency, average API cost per question, and usability as unavailable. Export timestamps and individual tool durations cannot substitute for these measurements.

**Status of target comparisons:** Section 5 proposes thresholds during documentation preparation; they are not established as targets registered before the experiments. “Met” and “Not met” therefore describe retrospective comparisons against proposed acceptance criteria.

The project has measurable experimental results but has not met all proposed targets. The next priorities are improving output validation, correcting evaluation reference data, and confirming answer quality using complete evidence and consistent scoring rules.
