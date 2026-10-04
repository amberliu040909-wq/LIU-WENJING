# EVALS README — Singapore Tourism Agent

Author: Liu Wenjing  
Project: PE6201 — Singapore Tourism RAG + Controlled Agent  
Experiments archived: 4 October 2026

## 1. Evaluation purpose

The evaluation measures whether the Agent selects expected tools, satisfies evidence-format rules, answers consistently with reference criteria, cites supporting sources, expresses uncertainty appropriately, and follows user constraints. It combines deterministic checks, LLM judging, and human review.

Snapshot correctness and current correctness are different. An answer may agree with a saved snapshot while giving an outdated price or closure notice. The submitted evaluation does not establish reliable same-day factual accuracy.

## 2. Code and experiment files

- `pe6201_singapore_tourism_agent_colab.py`: supplied full project script, including ingestion, tools, Agent creation, evaluation, and experiment saving.
- `evaluation_original.py`: extracted evaluation stages retaining the supplied script's original logic.
- `evaluation_colab.ipynb`: extracted notebook with corrected tool delimiters and protection against overwriting a completed review workbook.
- `evaluation_questions_30.xlsx` / `.csv`: questions, reference answers/criteria, and expected tools.
- `evaluation_results_<model>_raw.csv` / `.xlsx`: archived results before the saving stage's tool-score correction.
- `evaluation_results_<model>_corrected.csv` / `.xlsx`: results with tool selection recalculated using the documented matching rule.
- `automatic_summary_<model>.*`: automatic metric counts and rates.
- `human_review_10_<model>.*`: human scores and review notes.
- `human_summary_<model>.*`: human metric counts and rates.
- `judge_human_comparison_gpt6_1.*`: disagreement rates for GPT-6.1.
- `baseline_metadata.json`, `agent_instructions_<model>.txt`, `tool_audit_log_<model>.json`, and `file_manifest.csv`: configuration, instructions, available logs, and archive inventory.

Here, `<model>` is `gpt4o_mini` or `gpt6_1`. CSV and XLSX exports represent the same type of result, rather than independent experiments.

## 3. Model and human-review correspondence

| Item | GPT-4o-mini experiment | GPT-6.1 experiment |
|---|---|---|
| Configured model identifier | `openai/gpt-4o-mini` | `openai/gpt-6.1-sol-pro` |
| Archive | `gpt4o_mini_baseline_20261004_122103.zip` | `gpt6_1_baseline_20261004_144053.zip` |
| Original completed review | `human_review_10.xlsx` | `human_review_10_with_disagreements.xlsx` |
| Archived review | `human_review_10_gpt4o_mini.xlsx` | `human_review_10_gpt6_1.xlsx` / `.csv` |
| Automatically evaluated questions | 30 | 30 |
| Human-reviewed questions | 10 | 10 |

The workbook named `human_review_10.xlsx` belongs to GPT-4o-mini. The workbook named `human_review_10_with_disagreements.xlsx` belongs to GPT-6.1. Do not use one model's human scores to summarize the other model's generated answers.

The shared human-review IDs are Q01, Q06, Q09, Q13, Q15, Q19, Q21, Q24, Q25, and Q29. GPT-6.1's reviewed answer texts match its archived evaluation answers. GPT-4o-mini's reviewed answer texts do not exactly match its archived final evaluation rows, suggesting that the review relates to a different run/version. Consequently, the human model comparison is indicative rather than a fully paired comparison.

## 4. Procedure and reproduction

1. Mount Google Drive in Colab and configure the API client without submitting credentials.
2. Load the saved corpus/chunks, construct or load the matching FAISS index, define the four tools, and create the Agent.
3. Confirm `PROJECT_DIR`, `tourism_agent`, `OFFICIAL_DOMAINS`, `TOOL_AUDIT_LOG`, `openrouter_client`, and `OPENROUTER_MODEL` exist.
4. Load `PROJECT_DIR / evaluation_questions_30.xlsx` with pandas/openpyxl. Require exactly 30 rows, the expected columns, and a nonempty question in every row.
5. Evaluate sequentially using `await ask_agent(question)`. Each question starts with a cleared tool audit log. Record the answer, called tools, validator outcome, judge scores, and errors.
6. Compare actual tools with expected tools and ask the LLM judge to score the answer. A question-level exception is recorded and the next question continues.
7. Save the automatic results to CSV/XLSX.
8. Prepare the ten-item human-review workbook. Pause execution, inspect the answers against evidence and criteria, enter scores and notes, and save the workbook.
9. Read the completed review, calculate per-metric rates and judge–human disagreements, and archive model-labelled outputs with metadata.

The extracted notebook must use the same runtime and namespace as the Agent setup. Opening it separately does not share variables automatically. Its original Python extraction contains top-level `await` and is intended for notebook cells/inspection.

Run stages 1–3 of the extracted notebook before human review, and stages 4–5 afterward. Verify that any existing review contains answers from the current run. The archive stage retains the original GPT-6.1 saving logic; check the actual configured model before using it.

Recorded retrieval settings are the multilingual MiniLM embedding model, top-k 6, minimum similarity 0.25, and recorded temperature 0. Repeating the experiment can still change outputs because models and live websites can change.

## 5. Metric definitions

### Deterministic checks

| Metric | Definition |
|---|---|
| `tool_selection_correct` | 1 when the expected tool set is a subset of the actual called tool set; otherwise 0. Order is ignored, repeated calls collapse into a set, and additional tools are allowed. |
| `validator_passed` | 1 only when local knowledge-base search was called, at least one URL appears, every extracted URL matches an allowed official domain, and the answer contains a date matching YYYY-MM-DD. |

The tool parser supports comma, pipe, and semicolon separators. The supplied evaluation loop originally split only on pipes despite its comment. The saving stage recalculates corrected scores. Use corrected outputs for the reported tool-selection rates; retain raw results to explain the earlier 10% result.

Calling a tool does not prove the tool succeeded or returned relevant evidence. The validator checks structural conditions, not the truth, freshness, or source entailment of each claim. It can penalize a reasonable refusal or a date written in another format.

### LLM-judge scores

Each score is binary, with missing values when judging fails.

| Output field | Intended criterion |
|---|---|
| `judge_faithful` | Main factual claims are consistent with available evidence/reference criteria. |
| `judge_snapshot_correct` | Answer agrees with the frozen reference answer or satisfies its acceptable-answer criteria. |
| `judge_citation_support` | Cited official sources reasonably support the main factual claims. |
| `judge_uncertainty` | Missing, conflicting, outdated, or insufficient evidence is acknowledged when appropriate. |
| `judge_constraint_satisfaction` | Important question/rubric requirements are satisfied. |
| `judge_reason` | Short textual explanation of the judgment. |

The judge prompt accepts alternative reasonable itineraries and does not require word-for-word reference matching. It receives the question, reference answer/rubric, expected URL/title, abstention flag, and candidate answer. It does not receive the complete retrieved passages or independently open the citations. Faithfulness and citation scores are therefore estimates with limited evidence access.

The actual supplied script calls `OPENROUTER_MODEL` for judging, so changing the Agent model also changes the judge. Cross-model LLM scores are not measured by one fixed evaluator.

### Human scores and disagreement

Human reviewers use corresponding `human_*` columns for tool selection, faithfulness, snapshot correctness, citation support, uncertainty, constraints, and overall pass, plus `human_notes`.

Use 1 for passing the criterion, 0 for failing it, and N/A for an unassessable item. `human_overall_pass` records the reviewer's overall judgment; it should not be assumed to be the conjunction of all component scores. A separate current-correctness assessment is required before claiming today's facts were verified.

For each metric:

`pass rate = passed valid scores / number of valid scores`

Missing/N/A scores are excluded from the denominator. GPT-4o-mini snapshot correctness has nine valid reviews, while the other reported human metrics have ten.

Judge–human disagreement is the proportion of jointly scored items whose binary scores differ. Missing scores are excluded; a missing score is not itself a disagreement.

## 6. Results

### Automatic evaluation (30 questions per model)

| Metric | GPT-4o-mini | GPT-6.1 |
|---|---:|---:|
| Corrected tool selection | 46.7% (14/30) | 90.0% (27/30) |
| Validator pass | 43.3% (13/30) | 13.3% (4/30) |
| Judge faithfulness | 66.7% (20/30) | 23.3% (7/30) |
| Judge snapshot correctness | 43.3% (13/30) | 66.7% (20/30) |
| Judge citation support | 83.3% (25/30) | 60.0% (18/30) |
| Judge uncertainty | 46.7% (14/30) | 53.3% (16/30) |
| Judge constraint satisfaction | 66.7% (20/30) | 63.3% (19/30) |

### Human review

| Metric | GPT-4o-mini | GPT-6.1 |
|---|---:|---:|
| Human tool selection | 40.0% (4/10) | 100.0% (10/10) |
| Human faithfulness | 30.0% (3/10) | 80.0% (8/10) |
| Human snapshot correctness | 33.3% (3/9) | 80.0% (8/10) |
| Human citation support | 20.0% (2/10) | 90.0% (9/10) |
| Human uncertainty | 50.0% (5/10) | 90.0% (9/10) |
| Human constraint satisfaction | 40.0% (4/10) | 70.0% (7/10) |
| Human overall pass | 30.0% (3/10) | 80.0% (8/10) |

GPT-6.1 judge–human disagreement is 60% for faithfulness, 20% for snapshot correctness, 20% for citation support, 20% for uncertainty, and 10% for constraint satisfaction, each over ten jointly scored records.

## 7. Interpretation and limitations

GPT-6.1 selected expected tools more often and received stronger human scores in the submitted reviews. However, its validator and several judge scores decreased. These differences indicate that the metrics assess different aspects of performance and that the judging process is sensitive to evaluator choice and limited evidence access. An 80% human overall rate means eight reviewed answers passed; it does not mean 80% accuracy across all tourist questions.

The four tools include local search, route retrieval, direct official-page fetching, and live official web search. Adding the fourth tool did not solve all current-information failures. Dynamic booking pages, incomplete extraction, old closure notices, and date alignment still prevented reliable answers about today's prices or operating status.

Other limitations:

- Only 30 questions and ten human-reviewed items per model; the review subset is not established as a representative random sample.
- Subjective itinerary criteria allow multiple valid answers.
- Reference-answer quality is imperfect; GPT-4o-mini Q06 snapshot correctness is N/A because its reference answer is unrelated.
- GPT-4o-mini human review and archived final output are not perfectly paired.
- The judge model changes with the Agent model and lacks full retrieved evidence.
- GPT-4o-mini's saved audit log is empty; the other archive has available entries but should not be assumed to contain a complete historical trace.
- Missing judge scores are excluded from means; failures must also be examined through `evaluation_error`.
- End-to-end latency summaries, API cost per question, and user usability scores are unavailable.

A stronger follow-up evaluation would use a fixed independent judge, reviews paired with the exact saved outputs, corrected reference answers, dated live ground truth, claim-level citation checks, category-level results, and larger human samples. All reruns should be saved separately.

## 8. Submission location

Data and experiment packages are stored in the [Google Drive project folder](https://drive.google.com/drive/folders/1mbccWUCHCjk_eg2Xnz4ohil7ziP4As5t?usp=sharing). Submit this evaluation explanation alongside the separate DATA README, original/extracted evaluation code, both model archives, and model-specific human-review records.

