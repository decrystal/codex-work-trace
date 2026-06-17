from __future__ import annotations


def generate_summary(prompt: str, output: str) -> str:
    prompt_part = _first_sentence(prompt) or "No prompt provided"
    output_part = _first_sentence(output) or "No output provided"
    return f"Purpose: {prompt_part}. Result: {output_part}."


def summarize_session_increment(previous_summary: str, turn_summary: str) -> str:
    previous = previous_summary.strip()
    current = turn_summary.strip()
    if previous and current:
        return f"{previous} Next: {current}"
    return previous or current


def _first_sentence(text: str) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        return ""
    for separator in (".", "!", "?"):
        if separator in compact:
            compact = compact.split(separator, 1)[0]
            break
    return compact[:180].strip()
