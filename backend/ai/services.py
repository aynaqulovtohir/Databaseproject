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


def build_analysis_messages(submission):
    """AI'ga yuboriladigan matn. Talaba haqida hech qanday ma'lumot qo'shilmaydi."""
    assignment = submission.assignment
    return [
        {
            "role": "user",
            "content": prompts.ANALYSIS_USER_TEMPLATE.format(
                title=assignment.title,
                description=assignment.description,
                grading_criteria=assignment.grading_criteria.strip() or prompts.NO_CRITERIA_TEXT,
                sql_code=submission.sql_code,
            ),
        }
    ]


def analyze_submission(submission):
    """Yechimni tahlil qiladi. Qaytaradi: (AnalysisResult, input_tokens, output_tokens)."""
    response = create_message(
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
        max_tokens=CHAT_MAX_TOKENS,
        system=prompts.CHAT_SYSTEM_TEMPLATE.format(
            title=assignment.title, description=assignment.description
        ),
        messages=[*history, {"role": "user", "content": question}],
        output_config={"effort": "low"},
    )
    return extract_text(response)
