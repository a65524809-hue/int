"""LLM client: Gemini 2.5 Flash for interview answers (grounded in resume context)
and exam mode answers from on-screen MCQ screenshots. Auto-switches API key on
quota/rate limit."""
import os
import sys
from typing import Optional, Sequence, Union

from api_key_manager import (
    init_keys,
    get_current_key,
    get_keys,
    switch_to_next_key,
    is_quota_error,
)

RESUME_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume_context.txt")

PROMPT_TEMPLATE = (
    "You are a technical interview expert helping the candidate answer questions. "
    "Use ONLY the following resume/context to answer. If the question is about the candidate's projects, "
    "experience, skills, education, or certifications, base your answer strictly on this context. "
    "Keep answers concise, step-by-step when relevant, and under 300 words. "
    "If the question is general technical (e.g. DSA, OOP, testing) and not about the candidate, answer briefly from a technical perspective; you may still mention the candidate's relevant skills from the context where it fits.\n\n"
    "--- RESUME / CONTEXT ---\n{resume}\n--- END CONTEXT ---\n\n"
    "Interview question: {question}\n\n"
    "Answer (based on context when applicable):"
)

# Separate prompt for exam mode so it is NOT grounded in resume context
EXAM_PROMPT = (
    "You are in 'exam mode' helping a user solve a multiple-choice question from a screenshot. "
    "The screenshot will contain a single-question MCQ (possibly with diagrams, code, or tables) "
    "and several answer options like A), B), C), D) etc.\n\n"
    "Your job:\n"
    "1. Carefully read the entire question and ALL options from the screenshot.\n"
    "2. Identify the SINGLE best correct option.\n"
    "3. Respond with the full text of the correct option exactly as it appears in the screenshot, "
    "including the option label (for example: 'C) Binary search tree').\n\n"
    "Important rules:\n"
    "- Do NOT answer with only the letter (like 'C'). Always include the full option text.\n"
    "- If there is more than one correct option, choose the best or most complete one.\n"
    "- Do NOT mention that you saw a screenshot or that you are an AI model; just output the final answer.\n"
)

# Separate prompt for code mode
CODE_PROMPT = (
    "You are in 'code mode' helping a user solve a coding question (e.g., Leetcode-style) from a screenshot. "
    "The screenshot will contain a problem description, including any examples or constraints.\n\n"
    "Your job:\n"
    "1. Read the entire problem carefully.\n"
    "2. Write an optimal, bug-free solution in C++.\n"
    "3. Output exactly and ONLY the raw C++ code. Do NOT under any circumstances include any markdown formatting wrappers (like ```cpp or ```).\n"
    "4. Do NOT include explanations, comments about time complexity, intro/outro text, or conversational text. Simply output the raw code and nothing else.\n"
)

# Separate prompt for AMP mode
AMP_PROMPT = (
    "You are in 'AMP mode' helping a user solve a quantitative or aptitude question from a screenshot. "
    "The screenshot will contain a problem description, often mathematical, logical, or data interpretation.\n\n"
    "Your job:\n"
    "1. Read the entire problem carefully, including any possible multiple-choice options.\n"
    "2. Provide a clear, step-by-step logical derivation or mathematical solution.\n"
    "3. Explicitly state the final numerical answer or option chosen.\n"
    "4. Keep the explanation concise and easy to read quickly.\n"
)


def _load_resume_context() -> str:
    """Load resume context from resume_context.txt if present."""
    if os.path.isfile(RESUME_PATH):
        try:
            with open(RESUME_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[LLM] Could not load resume_context.txt: {e}", file=sys.stderr)
    return ""


def _call_gemini(
    api_key: str,
    model_name: str,
    contents: Union[str, Sequence[object]],
) -> Optional[str]:
    """
    Single attempt with one key. Returns response text or None on failure.

    `contents` can be a plain text prompt or a list combining text segments and images
    (for multimodal exam mode).
    """
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(contents)
    if not response or not getattr(response, "text", None):
        return None
    return response.text.strip()


def _run_with_key_rotation(
    contents: Union[str, Sequence[object]],
    config: dict,
) -> str:
    """Run a Gemini request with automatic API key rotation on quota/rate-limit errors."""
    init_keys(config)
    api_key = get_current_key()
    if not api_key:
        print("[LLM] No Gemini API key(s) set.", file=sys.stderr)
        return "[Configure gemini_api_key or gemini_api_keys in config.json]"

    model_name = config.get("llm_model") or "gemini-2.5-flash"
    key_list = get_keys()
    keys_available = len(key_list)
    keys_tried = 0

    while keys_tried < keys_available:
        try:
            text = _call_gemini(api_key, model_name, contents)
            if text:
                return text
            return "[No response from model]"
        except Exception as e:
            if is_quota_error(e) and keys_available > 1:
                next_key = switch_to_next_key()
                if next_key:
                    api_key = next_key
                    keys_tried += 1
                    continue
                print(f"[LLM] All {keys_available} keys hit quota.", file=sys.stderr)
                return "[Quota exceeded on all keys. Try again later.]"
            print(f"[LLM] Gemini error: {e}", file=sys.stderr)
            return f"[Error: {e}]"

    return "[Quota exceeded on all keys. Try again later.]"


def get_answer(question: str, config: dict) -> str:
    """Send a text question to Gemini, grounded in resume context when available."""
    resume = _load_resume_context()
    if not resume:
        resume = "(No resume_context.txt found; answer from general knowledge only.)"
    prompt = PROMPT_TEMPLATE.format(resume=resume, question=question)
    return _run_with_key_rotation(prompt, config)


def get_exam_answer_from_image(image, config: dict) -> str:
    """
    Send an MCQ screenshot to Gemini and return the best answer.

    - `image` is expected to be a PIL.Image.Image instance or any image object
      supported by google-generativeai.
    - The prompt instructs the model to answer with the FULL correct option text,
      not just 'A/B/C/D'.
    """
    contents = [EXAM_PROMPT, image]
    return _run_with_key_rotation(contents, config)


def get_code_answer_from_image(image, config: dict) -> str:
    """
    Send a coding problem screenshot to Gemini and return the raw C++ code answer.

    - `image` is expected to be a PIL.Image.Image instance or any image object
      supported by google-generativeai.
    - The prompt instructs the model to output ONLY raw C++ code without markdown formatting.
    """
    contents = [CODE_PROMPT, image]
    return _run_with_key_rotation(contents, config)


def get_amp_answer_from_image(image, config: dict) -> str:
    """
    Send an aptitude/quantitative problem screenshot to Gemini and return the step-by-step answer.
    """
    contents = [AMP_PROMPT, image]
    return _run_with_key_rotation(contents, config)
