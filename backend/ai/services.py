"""AI tahlili va chat javobi mantiqi."""
import json
from typing import Literal

from pydantic import BaseModel, ValidationError

from . import prompts
from .client import AIPermanentError, create_message, extract_text

ANALYSIS_MAX_TOKENS = 16000
CHAT_MAX_TOKENS = 8000


class Issue(BaseModel):
    title: str
    explanation: str
    severity: Literal["low", "medium", "high"]


class AnalysisResult(BaseModel):
    summary: str
    issues: list[Issue]
    recommendations: list[str]
    suggested_score: int
    score_rationale: str


def rubric_text(assignment, stage):
    """Shu yechim baholanadigan rubrika mezonlari (bosqichli loyihada — faqat shu bosqichniki)."""
    from learning.rubric import criteria_for

    criteria = criteria_for(assignment, stage)
    if not criteria:
        return ""
    lines = [
        f"- {item['name']} ({item['points']} ball)" + (f": {item['description']}" if item["description"] else "")
        for item in criteria
    ]
    total = sum(item["points"] for item in criteria)
    return (
        f"Rubrika (jami {total} ball):\n" + "\n".join(lines)
        + "\nTaklif qilinadigan ballni baribir 0–100 shkalada ber: 100 — shu mezonlarning barchasi to'liq bajarilgan."
    )


def build_analysis_messages(submission):
    """AI'ga yuboriladigan matn. Talaba haqida hech qanday ma'lumot qo'shilmaydi."""
    assignment = submission.assignment
    stage = submission.stage
    description = assignment.description
    if stage:
        description += (
            f"\n\nBu yechim loyihaning {stage.order + 1}-bosqichi uchun: «{stage.title}»."
            + (f"\nBosqich sharti: {stage.description}" if stage.description else "")
            + "\nFaqat shu bosqich talablarini baholang."
        )
    criteria = "\n\n".join(part for part in (assignment.grading_criteria.strip(), rubric_text(assignment, stage)) if part)
    return [
        {
            "role": "user",
            "content": prompts.ANALYSIS_USER_TEMPLATE.format(
                title=assignment.title,
                description=description,
                grading_criteria=criteria or prompts.NO_CRITERIA_TEXT,
                sql_code=submission.sql_code,
            ),
        }
    ]


def analyze_submission(submission):
    """Yechimni tahlil qiladi. Qaytaradi: (AnalysisResult, input_tokens, output_tokens)."""
    response = create_message(
        purpose="analysis",
        max_tokens=ANALYSIS_MAX_TOKENS,
        system=prompts.ANALYSIS_SYSTEM_PROMPT,
        messages=build_analysis_messages(submission),
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": prompts.ANALYSIS_JSON_SCHEMA},
        },
    )
    try:
        result = AnalysisResult.model_validate(json.loads(extract_text(response)))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIPermanentError("AI javobi kutilgan tuzilmada emas.") from exc

    # Ball har doim 0-100 oralig'ida bo'lishi kafolatlanadi
    result.suggested_score = max(0, min(100, result.suggested_score))
    return result, response.usage.input_tokens, response.usage.output_tokens


def chat_reply(assignment, history, question):
    """Talaba savoliga AI javobi.

    history: [{"role": "user" | "assistant", "content": "..."}] - oldingi xabarlar.
    Baholash mezonlari bu yerga ataylab qo'shilmaydi: ular talabaga ko'rinmasligi kerak.
    """
    response = create_message(
        purpose="chat",
        max_tokens=CHAT_MAX_TOKENS,
        system=prompts.CHAT_SYSTEM_TEMPLATE.format(
            title=assignment.title, description=assignment.description
        ),
        messages=[*history, {"role": "user", "content": question}],
        output_config={"effort": "low"},
    )
    return extract_text(response)
