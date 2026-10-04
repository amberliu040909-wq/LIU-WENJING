# ============================================================
# 30-question Agent evaluation
# 从Google Drive读取XLSX并进行异步评估
# ============================================================

import re
import json
import asyncio
from pathlib import Path

import pandas as pd


# ------------------------------------------------------------
# 1. Excel文件路径
# ------------------------------------------------------------

eval_path = PROJECT_DIR / "evaluation_questions_30.xlsx"

if not eval_path.exists():
    raise FileNotFoundError(
        f"找不到评估文件：{eval_path}\n"
        "请确认文件已经保存为真正的XLSX文件，"
        "而不是Google Sheets的.gsheet快捷方式。"
    )

print("Evaluation file:", eval_path)


# ------------------------------------------------------------
# 2. 读取Excel
# ------------------------------------------------------------

questions = pd.read_excel(
    eval_path,
    engine="openpyxl",
)

# 清理列名两侧空格
questions.columns = [
    str(column).strip()
    for column in questions.columns
]

required_columns = [
    "question_id",
    "category",
    "question",
    "expected_answer_from_snapshot",
    "expected_url_or_title",
    "expected_tools",
    "should_abstain",
    "time_sensitive",
    "notes",
]

missing_columns = [
    column
    for column in required_columns
    if column not in questions.columns
]

if missing_columns:
    raise RuntimeError(
        "Excel缺少以下列："
        + ", ".join(missing_columns)
    )

if len(questions) != 30:
    raise RuntimeError(
        f"评估集必须正好有30题，目前读取到{len(questions)}题。"
    )

if not questions["question"].fillna("").astype(str).str.strip().ne("").all():
    empty_rows = (
        questions.index[
            questions["question"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
        ]
        + 2
    ).tolist()

    raise RuntimeError(
        "以下Excel行的question为空："
        + ", ".join(map(str, empty_rows))
    )

print(f"Successfully loaded {len(questions)} questions.")
display(questions.head())


# ------------------------------------------------------------
# 3. 辅助函数
# ------------------------------------------------------------

def clean_cell(value):
    """把Excel空值转换为空字符串。"""

    if pd.isna(value):
        return ""

    return str(value).strip()


def parse_tool_set(value):
    """
    同时支持以下分隔符：
    search_knowledge_base | search_live_official_web
    search_knowledge_base, search_live_official_web
    search_knowledge_base; search_live_official_web
    """

    value = clean_cell(value)

    return {
        tool_name.strip()
        for tool_name in value.split("|")
        if tool_name.strip()
    }


def extract_json_object(text):
    """从模型输出中提取JSON对象。"""

    text = str(text or "").strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            flags=re.DOTALL,
        )

        if match:
            return json.loads(match.group(0))

        raise


# ------------------------------------------------------------
# 4. OpenRouter LLM Judge
# ------------------------------------------------------------

async def judge_agent_answer(
    question,
    expected,
    expected_url_or_title,
    should_abstain,
    answer,
):
    """
    使用OpenRouter评估Agent回答。

    expected是评估标准或参考答案，不要求Agent逐字匹配。
    """

    question = clean_cell(question)
    expected = clean_cell(expected)
    expected_url_or_title = clean_cell(
        expected_url_or_title
    )
    answer = clean_cell(answer)

    prompt = f"""
Return one valid JSON object only.

Use exactly these keys:
{{
  "faithful_to_available_evidence": 0,
  "correct_against_snapshot": 0,
  "citation_support": 0,
  "appropriate_uncertainty": 0,
  "constraint_satisfaction": 0,
  "concise_reason": ""
}}

Scoring instructions:

1. Each numerical field must be either 0 or 1.
2. The expected answer may be a reference answer or an evaluation rubric.
3. It is not necessarily the only acceptable answer.
4. Multiple different itineraries or recommendations may be correct.
5. Do not penalize a candidate only because it uses a different reasonable
   itinerary, attraction, route or ordering.
6. Evaluate whether factual claims are supported by the available evidence.
7. Penalize invented opening hours, prices, routes, accessibility features,
   closures or unsupported claims.
8. Citation support is 1 only when the cited official sources reasonably
   support the main factual claims.
9. Appropriate uncertainty is 1 when the answer clearly acknowledges missing,
   conflicting, outdated or insufficient evidence when necessary.
10. Constraint satisfaction is 1 when the candidate satisfies the important
    requirements in the question and evaluation criteria.
11. If should_abstain is true, a careful evidence-based refusal may be correct.

Question:
{question}

Expected answer or evaluation criteria:
{expected}

Expected official URL or source title:
{expected_url_or_title}

Should the Agent abstain:
{should_abstain}

Candidate answer:
{answer}
"""

    try:
        response = await openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an evaluation judge. "
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        raw = (
            response.choices[0]
            .message.content
            or ""
        ).strip()

        result = extract_json_object(raw)

        # 保证评分字段只能是0或1
        score_fields = [
            "faithful_to_available_evidence",
            "correct_against_snapshot",
            "citation_support",
            "appropriate_uncertainty",
            "constraint_satisfaction",
        ]

        for field in score_fields:
            value = result.get(field)

            try:
                result[field] = 1 if int(value) == 1 else 0
            except Exception:
                result[field] = None

        return result

    except Exception as exc:
        return {
            "faithful_to_available_evidence": None,
            "correct_against_snapshot": None,
            "citation_support": None,
            "appropriate_uncertainty": None,
            "constraint_satisfaction": None,
            "concise_reason": (
                "Judge failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        }


# ------------------------------------------------------------
# 5. 开始评估
# ------------------------------------------------------------

evaluation_rows = []

# 测试时可以改成2；正式评估改成30
EVALUATION_LIMIT = 30

for row_number, (_, item) in enumerate(
    questions.head(EVALUATION_LIMIT).iterrows(),
    start=1,
):
    question_id = clean_cell(
        item["question_id"]
    )

    question = clean_cell(
        item["question"]
    )

    expected = clean_cell(
        item["expected_answer_from_snapshot"]
    )

    expected_url_or_title = clean_cell(
        item["expected_url_or_title"]
    )

    expected_tools = parse_tool_set(
        item["expected_tools"]
    )

    should_abstain = clean_cell(
        item["should_abstain"]
    )

    print(
        f"[{row_number}/{EVALUATION_LIMIT}] "
        f"{question_id}: {question}"
    )

    try:
        # ask_agent是异步函数，因此必须使用await
        generated = await ask_agent(
            question
        )

        answer = clean_cell(
            generated.get("answer", "")
        )

        validation = (
            generated.get("validation", {})
            or {}
        )

        tools_called_list = (
            validation.get("tools_called", [])
            or []
        )

        actual_tools = {
            str(tool).strip()
            for tool in tools_called_list
            if str(tool).strip()
        }

        # 只要求预期工具是实际工具的子集
        # Agent可以合理地使用额外工具
        tool_selection_correct = (
            expected_tools.issubset(
                actual_tools
            )
        )

        judge = await judge_agent_answer(
            question=question,
            expected=expected,
            expected_url_or_title=(
                expected_url_or_title
            ),
            should_abstain=should_abstain,
            answer=answer,
        )

        evaluation_rows.append({
            **item.to_dict(),

            "answer": answer,

            "actual_tools": " | ".join(
                sorted(actual_tools)
            ),

            "tool_selection_correct": (
                tool_selection_correct
            ),

            "validator_passed": validation.get(
                "passed"
            ),

            "judge_faithful": judge.get(
                "faithful_to_available_evidence"
            ),

            "judge_snapshot_correct": judge.get(
                "correct_against_snapshot"
            ),

            "judge_citation_support": judge.get(
                "citation_support"
            ),

            "judge_uncertainty": judge.get(
                "appropriate_uncertainty"
            ),

            "judge_constraint_satisfaction": judge.get(
                "constraint_satisfaction"
            ),

            "judge_reason": judge.get(
                "concise_reason"
            ),

            "evaluation_error": "",
        })

    except Exception as exc:
        # 一题失败时继续评估下一题
        evaluation_rows.append({
            **item.to_dict(),

            "answer": "",

            "actual_tools": "",

            "tool_selection_correct": False,

            "validator_passed": False,

            "judge_faithful": None,

            "judge_snapshot_correct": None,

            "judge_citation_support": None,

            "judge_uncertainty": None,

            "judge_constraint_satisfaction": None,

            "judge_reason": "",

            "evaluation_error": (
                f"{type(exc).__name__}: {exc}"
            ),
        })

        print(
            f"Question {question_id} failed: "
            f"{type(exc).__name__}: {exc}"
        )

    # 减少OpenRouter连续请求过快的问题
    await asyncio.sleep(1)


# ------------------------------------------------------------
# 6. 保存结果
# ------------------------------------------------------------

evaluation = pd.DataFrame(
    evaluation_rows
)

csv_output_path = (
    PROJECT_DIR
    / "evaluation_results_agent.csv"
)

xlsx_output_path = (
    PROJECT_DIR
    / "evaluation_results_agent.xlsx"
)

evaluation.to_csv(
    csv_output_path,
    index=False,
    encoding="utf-8-sig",
)

evaluation.to_excel(
    xlsx_output_path,
    index=False,
    engine="openpyxl",
)

print("\nEvaluation completed.")
print("CSV result:", csv_output_path)
print("XLSX result:", xlsx_output_path)


# ------------------------------------------------------------
# 7. 显示结果
# ------------------------------------------------------------

display(
    evaluation.head()
)

score_columns = [
    "tool_selection_correct",
    "validator_passed",
    "judge_faithful",
    "judge_snapshot_correct",
    "judge_citation_support",
    "judge_uncertainty",
    "judge_constraint_satisfaction",
]

display(
    evaluation[
        score_columns
    ]
    .apply(
        pd.to_numeric,
        errors="coerce",
    )
    .mean()
    .to_frame("mean")
)

