from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CONTEXT_FILE = Path(
    os.getenv("SLANG_CONTEXT_FILE", BASE_DIR / "data" / "slang_context.json")
)
AI_API_ENDPOINT = os.getenv(
    "AI_API_ENDPOINT",
    "https://hackathon-1pvb.onrender.com/api/ai-model/v2/chat",
).strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
REQUEST_TIMEOUT_SECONDS = 20
MAX_CONTEXT_GUIDANCE_CHARS = 700
MAX_STYLE_TERMS = 8
MAX_RELEVANT_HINTS = 6
MAX_TONE_NOTES = 3

STYLE_STOPWORDS = {
    "a", "ahora", "ahi", "al", "algo", "alguien", "an", "and", "ante", "are",
    "asi", "at", "aun", "aunque", "ay", "bien", "but", "by", "casi", "como",
    "con", "de", "del", "demasiado", "desde", "di", "dia", "donde", "dos", "el",
    "ella", "en", "era", "eres", "es", "esa", "ese", "eso", "esta", "está",
    "estaba", "estado", "estan", "están", "estar", "estoy", "esto", "este",
    "estuvo", "estuve", "hace", "hay",
    "he", "here", "hoy", "i", "in", "ir", "is", "it", "la", "las", "le", "lo",
    "los", "mas", "me", "mi", "mio", "mis", "mucho", "muy", "my", "na", "no",
    "nos", "nuestra", "nuestro", "o", "otra", "otro", "pa", "pal", "pero", "por",
    "porque", "que", "qué", "quiero", "se", "ser", "si", "sin", "so", "su", "sus",
    "te", "the", "this", "to", "todo", "too", "tu", "tú", "un", "una", "uno",
    "va", "vamos", "voy", "we", "what", "when", "with", "ya", "yo",
    "aqui", "aquí", "casa", "calor", "carro", "clase", "comida", "conversation",
    "día", "estaba", "example", "filler", "full", "game", "gente", "line", "lugar",
    "mal", "mall", "movie", "mucha", "necesito", "number", "otra", "parking",
    "playa", "queda", "quedo", "quedó", "rato", "serie", "sitio", "sueño", "text",
    "testing", "trabajo", "trip", "vamo", "vamos", "video", "weekend",
}

REFUSAL_MARKERS = (
    "i'm sorry, but i can't help with that",
    "i’m sorry, but i can’t help with that",
    "outside stem educational topics",
)

app = Flask(__name__, template_folder="templates", static_folder="static")


class TranslationError(RuntimeError):
    def __init__(self, message: str, *, can_fallback: bool = False) -> None:
        super().__init__(message)
        self.can_fallback = can_fallback


def normalize_api_key(api_key: str) -> str:
    cleaned = api_key.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("sk_"):
        return cleaned
    return f"sk_{cleaned}"


def empty_slang_context() -> dict[str, list[Any]]:
    return {
        "tone_notes": [],
        "glossary": [],
        "examples": [],
    }


def load_slang_context() -> dict[str, list[Any]]:
    try:
        raw_text = CONTEXT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return empty_slang_context()

    if not raw_text:
        return empty_slang_context()

    try:
        return parse_slang_context(json.loads(raw_text))
    except json.JSONDecodeError as exc:
        raise TranslationError(
            f"The slang context JSON file is invalid: {CONTEXT_FILE.name}.",
        ) from exc


def normalize_context_text(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'").replace("`", "'")


def normalize_glossary_entries(raw_glossary: Any) -> list[tuple[str, str]]:
    glossary: list[tuple[str, str]] = []

    if isinstance(raw_glossary, dict):
        iterable = raw_glossary.items()
        for source, target in iterable:
            source_text = str(source).strip()
            target_text = str(target).strip()
            if source_text and target_text:
                glossary.append((source_text, target_text))

    elif isinstance(raw_glossary, list):
        for item in raw_glossary:
            if isinstance(item, dict):
                source = item.get("source", item.get("from", ""))
                target = item.get("target", item.get("to", ""))
                source_text = str(source).strip()
                target_text = str(target).strip()
                if source_text and target_text:
                    glossary.append((source_text, target_text))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                source_text = str(item[0]).strip()
                target_text = str(item[1]).strip()
                if source_text and target_text:
                    glossary.append((source_text, target_text))
            elif isinstance(item, str) and "=>" in item:
                source, target = [part.strip() for part in item.split("=>", 1)]
                if source and target:
                    glossary.append((source, target))

    return sorted(glossary, key=lambda item: len(item[0]), reverse=True)


def parse_legacy_slang_context_text(slang_context: str) -> dict[str, list[Any]]:
    tone_notes: list[str] = []
    glossary: list[tuple[str, str]] = []
    examples: list[str] = []

    for raw_line in normalize_context_text(slang_context).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        lowered = line.casefold().rstrip(":")
        if lowered in {"tone notes", "vocabulary"}:
            continue

        if line.startswith("-"):
            note = line[1:].strip()
            if note:
                tone_notes.append(note)
            continue

        if "=>" in line:
            source, target = [part.strip() for part in line.split("=>", 1)]
            if source and target:
                glossary.append((source, target))
            continue

        examples.append(line)

    glossary.sort(key=lambda item: len(item[0]), reverse=True)
    return {
        "tone_notes": tone_notes,
        "glossary": glossary,
        "examples": examples,
    }


def parse_slang_context(slang_context: Any) -> dict[str, list[Any]]:
    if not slang_context:
        return empty_slang_context()

    if isinstance(slang_context, dict):
        tone_notes = [
            str(note).strip()
            for note in slang_context.get("tone_notes", [])
            if str(note).strip()
        ]
        examples = [
            str(example).strip()
            for example in slang_context.get("examples", [])
            if str(example).strip()
        ]
        glossary_source = slang_context.get("glossary", slang_context.get("vocabulary", {}))
        glossary = normalize_glossary_entries(glossary_source)
        return {
            "tone_notes": tone_notes,
            "glossary": glossary,
            "examples": examples,
        }

    if isinstance(slang_context, str):
        cleaned = slang_context.strip()
        if not cleaned:
            return empty_slang_context()

        if cleaned.startswith("{") or cleaned.startswith("["):
            try:
                return parse_slang_context(json.loads(cleaned))
            except json.JSONDecodeError:
                pass

        return parse_legacy_slang_context_text(cleaned)

    return empty_slang_context()


def extract_keywords(text: str) -> set[str]:
    normalized = normalize_context_text(text).casefold()
    tokens = re.findall(r"[a-záéíóúñü']+", normalized)
    return {
        token
        for token in tokens
        if len(token) >= 3 and token not in STYLE_STOPWORDS
    }


def select_relevant_glossary(user_text: str, glossary: list[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized_user_text = normalize_context_text(user_text).casefold()
    user_keywords = extract_keywords(user_text)
    ranked: list[tuple[int, int, str, str]] = []

    for source, target in glossary:
        normalized_source = normalize_context_text(source).casefold()
        source_keywords = extract_keywords(source)

        score = 0
        if normalized_source and normalized_source in normalized_user_text:
            score += 10 + len(normalized_source.split())

        keyword_overlap = len(source_keywords & user_keywords)
        if keyword_overlap:
            score += keyword_overlap * 4

        if score:
            ranked.append((score, len(source), source, target))

    ranked.sort(reverse=True)
    return [(source, target) for _score, _length, source, target in ranked[:MAX_RELEVANT_HINTS]]


def derive_style_terms(
    glossary: list[tuple[str, str]],
    examples: list[str],
) -> list[str]:
    counts: Counter[str] = Counter()

    for _source, target in glossary:
        for token in extract_keywords(target):
            counts[token] += 3

    for example in examples:
        for token in extract_keywords(example):
            counts[token] += 1

    return [term for term, _count in counts.most_common(MAX_STYLE_TERMS)]


def build_context_guidance(user_text: str, slang_context: str) -> str:
    parsed_context = parse_slang_context(slang_context)
    tone_notes = parsed_context["tone_notes"][:MAX_TONE_NOTES]
    glossary = parsed_context["glossary"]
    examples = parsed_context["examples"]
    style_terms = derive_style_terms(glossary, examples)
    relevant_glossary = select_relevant_glossary(user_text, glossary)

    def render_guidance(
        notes: list[str],
        terms: list[str],
        hints: list[tuple[str, str]],
    ) -> str:
        lines: list[str] = []

        if notes:
            lines.append("Tone guidance from the local vocab file:")
            lines.extend(f"- {note}" for note in notes)

        if terms:
            lines.append("Common boricua flavor words from that file:")
            lines.append(f"- {', '.join(terms)}")

        if hints:
            lines.append("Prefer these direct glossary hints over other slang synonyms when they fit this sentence naturally:")
            lines.extend(f"- {source} -> {target}" for source, target in hints)
        else:
            lines.append("There are no direct glossary matches for this sentence, so keep the boricua tone without forcing vocab.")

        return "\n".join(lines)

    guidance = render_guidance(tone_notes, style_terms, relevant_glossary)
    while len(guidance) > MAX_CONTEXT_GUIDANCE_CHARS:
        if len(relevant_glossary) > 2:
            relevant_glossary = relevant_glossary[:-1]
        elif len(style_terms) > 4:
            style_terms = style_terms[:-1]
        elif len(tone_notes) > 1:
            tone_notes = tone_notes[:-1]
        else:
            break
        guidance = render_guidance(tone_notes, style_terms, relevant_glossary)

    return guidance or "Keep the translation natural, boricua, and concise."


def build_prompt(user_text: str, slang_context: str) -> str:
    context_guidance = build_context_guidance(user_text, slang_context)
    return f"""
You are helping with a STEM education demo app called "Asi Se Dice".
The app rewrites student-facing text into natural Puerto Rican slang and light Spanglish.

Use the local vocabulary file as tone guidance. Do not dump or summarize the whole file.
Let it shape the translator's voice and vocabulary choices instead.

Rules:
- Keep the user's meaning intact.
- Sound natural in Puerto Rico.
- Do not force a slang word if it makes the sentence sound grammatically wrong.
- When a direct glossary hint is provided for this sentence, prefer that wording over a different slang synonym.
- It is better to ignore a vocab hint than to produce an awkward phrase.
- Keep the answer concise and readable.
- Avoid slurs or hateful language.
- Return only the translated phrase.

Vocabulary and tone guidance:
{context_guidance}

User text:
{user_text}
""".strip()


def strip_reasoning(text: str) -> str:
    cleaned = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = cleaned.replace("\r", "").strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return " ".join(lines)


def extract_translation(payload: Any) -> str:
    if isinstance(payload, str):
        return strip_reasoning(payload)

    if isinstance(payload, dict):
        direct_keys = ("response", "result", "text", "message", "prompt", "content")
        for key in direct_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return strip_reasoning(value)

        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return strip_reasoning(content)

        return ""

    return strip_reasoning(str(payload))


def extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "The AI API returned an unknown error."

    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "status"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return "The AI API returned an unknown error."


def looks_like_refusal(text: str) -> bool:
    normalized = text.casefold()
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def request_ai_translation(user_text: str, slang_context: str) -> str:
    api_key = normalize_api_key(AI_API_KEY)
    if not AI_API_ENDPOINT or not api_key:
        raise TranslationError(
            "The AI endpoint is not configured yet. Add AI_API_ENDPOINT and AI_API_KEY in .env.",
            can_fallback=True,
        )

    prompt = build_prompt(user_text, slang_context)

    try:
        response = requests.post(
            AI_API_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": api_key,
            },
            json={"context": prompt},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise TranslationError(
            "Could not reach the hosted AI model.",
            can_fallback=True,
        ) from exc

    if not response.ok:
        message = extract_error_message(response)
        can_fallback = "outside allowed hackathon topics" in message.casefold()
        raise TranslationError(message, can_fallback=can_fallback)

    try:
        payload = response.json()
    except ValueError as exc:
        raise TranslationError(
            "The AI API returned a response that could not be decoded.",
            can_fallback=True,
        ) from exc

    translation = extract_translation(payload)
    if not translation:
        raise TranslationError(
            "The AI API returned an empty translation.",
            can_fallback=True,
        )

    if looks_like_refusal(translation):
        raise TranslationError(translation, can_fallback=True)

    return translation


def parse_replacement_pairs(slang_context: str) -> list[tuple[str, str]]:
    return parse_slang_context(slang_context)["glossary"]


def apply_case_pattern(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def apply_replacements(text: str, replacements: list[tuple[str, str]]) -> tuple[str, bool]:
    updated_text = text
    changed = False

    for source, target in replacements:
        pattern = re.compile(rf"\b{re.escape(source)}\b", flags=re.IGNORECASE)

        def _swap(match: re.Match[str]) -> str:
            nonlocal changed
            changed = True
            return apply_case_pattern(match.group(0), target)

        updated_text = pattern.sub(_swap, updated_text)

    return updated_text, changed


def add_soft_flair(text: str) -> str:
    if not text:
        return text

    lower_text = text.casefold()
    if any(marker in lower_text for marker in ("mano", "pana", "acho", "wepa")):
        return text

    punctuation = ""
    if text[-1] in ".!?":
        punctuation = text[-1]
        text = text[:-1]

    return f"{text}, mano{punctuation or '.'}"


def fallback_translate(user_text: str, slang_context: str) -> str:
    default_pairs = [
        ("right now", "ahora mismito"),
        ("my friend", "mi pana"),
        ("friend", "pana"),
        ("tired", "cansao"),
        ("cool", "nitido"),
        ("awesome", "brutal"),
        ("great", "durisimo"),
        ("problem", "revolu"),
        ("issue", "revolu"),
        ("stopped working", "dejo de bregar"),
        ("not working", "no esta bregando"),
        ("money", "chavos"),
        ("hang out", "janguear"),
        ("party", "jangueo"),
        ("hello", "wepa"),
        ("amigo", "pana"),
        ("cansado", "cansao"),
        ("genial", "nitido"),
        ("problema", "revolu"),
        ("dejo de funcionar", "dejo de bregar"),
        ("no funciona", "no esta bregando"),
        ("dinero", "chavos"),
        ("ahora mismo", "ahora mismito"),
        ("fiesta", "jangueo"),
        ("salir", "janguear"),
    ]
    context_pairs = parse_replacement_pairs(slang_context)
    replacements = context_pairs + default_pairs

    translated, changed = apply_replacements(user_text.strip(), replacements)
    if not changed:
        translated = add_soft_flair(user_text.strip())

    return translated


def translate_text(user_text: str) -> tuple[str, str, str]:
    slang_context = load_slang_context()

    try:
        translation = request_ai_translation(user_text, slang_context)
        return translation, "api", "Live AI translation with vocabulary context."
    except TranslationError as exc:
        if not exc.can_fallback:
            raise

    translation = fallback_translate(user_text, slang_context)
    return translation, "fallback", "Local slang fallback used because the hosted model refused or was unavailable."


@app.route("/")
def home() -> str:
    return render_template("index.html")


@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json(silent=True) or {}
    user_text = data.get("text", "").strip()

    if not user_text:
        return jsonify({"error": "Please type something first."}), 400

    try:
        translation, source, note = translate_text(user_text)
    except TranslationError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception:
        return jsonify({"error": "Something went wrong while translating."}), 500

    return jsonify(
        {
            "original": user_text,
            "translation": translation,
            "source": source,
            "note": note,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
