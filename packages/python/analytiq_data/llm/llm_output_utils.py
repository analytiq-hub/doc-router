import re


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

    Uses ``extract_json_from_resp_content`` for all providers. That helper is a
    no-op for bare JSON objects and handles markdown fences, reasoning blocks, and
    outermost ``{ ... }`` extraction when models ignore strict JSON mode.
    """
    _ = llm_provider  # reserved for provider-specific handling if needed later
    return extract_json_from_resp_content(resp_content)