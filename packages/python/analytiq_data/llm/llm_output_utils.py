import re
import json
from typing import Optional


def extract_json_from_resp_content(resp_content: str) -> str:
    """
    Extract a JSON object string from raw LLM response content.

    Safe to apply to any provider's output:
    - If content is already a bare JSON object, only whitespace is trimmed.
    - Otherwise, strips reasoning/think blocks, unwraps ```json ... ``` fences,
      and falls back to the outermost `{ ... }` span.

    This is needed because reasoning-capable models (Groq DeepSeek, Moonshot
    Kimi via Azure Foundry, etc.) interleave `<think>...</think>` or markdown
    fences with the JSON, even when the system prompt asks for JSON only.
    """
    if not resp_content:
        return resp_content

    # Remove <think>...</think> blocks (reasoning models)
    resp_content = re.sub(r'<think>.*?</think>', '', resp_content, flags=re.DOTALL)

    resp_content = resp_content.strip()

    # Unwrap ```json ... ``` (or generic ``` ... ```) fences
    if resp_content.startswith("```json"):
        resp_content = resp_content[7:]
        resp_content = resp_content.split("```")[0]
        resp_content = resp_content.strip()
    elif resp_content.startswith("```"):
        resp_content = resp_content[3:]
        resp_content = resp_content.split("```")[0]
        resp_content = resp_content.strip()
    elif "```json" in resp_content:
        start = resp_content.find("```json") + 7
        end = resp_content.find("```", start)
        if end != -1:
            resp_content = resp_content[start:end].strip()

    # Fall back to the outermost JSON object span if we still aren't at one
    if not resp_content.startswith('{'):
        start = resp_content.find('{')
        end = resp_content.rfind('}')
        if start != -1 and end != -1 and end > start:
            resp_content = resp_content[start:end + 1]

    return resp_content

def process_llm_resp_content(resp_content: str, llm_provider: str) -> str:
    """
    Process an LLM response into a parseable JSON object string.

    Only `groq` and `azure_ai` get the aggressive cleanup, because the
    reasoning models served on those providers (Groq DeepSeek, Moonshot
    Kimi via Azure Foundry, etc.) interleave `<think>...</think>` blocks
    or wrap JSON in markdown fences even when the system prompt asks
    for JSON only, and neither provider supports strict JSON schema mode.

    Other providers (OpenAI, Anthropic, Gemini, Bedrock, Vertex, XAI)
    honor `response_format` and return clean JSON, so we leave their
    output untouched aside from stripping whitespace.

    Args:
        resp_content: Raw response content from the LLM.
        llm_provider: The LLM provider (e.g. "groq", "azure_ai", "openai").

    Returns:
        str: Cleaned JSON string ready for parsing.
    """
    if llm_provider in ("groq", "azure_ai"):
        return extract_json_from_resp_content(resp_content)

    return resp_content.strip() if resp_content else resp_content