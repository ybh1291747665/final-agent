"""LLM generation with hallucination guard."""

from final_agent.generation.answer_generator import answer_question, generate_review, generate_exam
from final_agent.generation.llm_client import generate, generate_stream
from final_agent.generation.guard import verify_answer
from final_agent.generation.prompts import SYSTEM_PROMPT, QA_PROMPT, REVIEW_PROMPT, EXAM_PROMPT

__all__ = [
    "answer_question",
    "generate_review",
    "generate_exam",
    "generate",
    "generate_stream",
    "verify_answer",
    "SYSTEM_PROMPT",
    "QA_PROMPT",
    "REVIEW_PROMPT",
    "EXAM_PROMPT",
]
