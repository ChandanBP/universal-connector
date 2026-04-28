"""
UNIVERSAL CONNECTOR — Intent Parser
Domain-agnostic: all domain knowledge comes from DomainConfig.

Converts a natural language query into a Structured Intent Object.
The LLM system prompt is generated from the domain config — no
domain-specific vocabulary or field names are hardcoded here.

Usage:
  from engine.domains import get_domain
  from engine.intent_parser import parse_intent

  config = get_domain('restaurants')
  intent = parse_intent("quiet North Indian in Indiranagar for a business dinner", config)
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

try:
    from groq import Groq
    _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except ImportError:
    raise ImportError("Run: pip install groq")

from engine.domains.base import DomainConfig, IntentField, IntentObject

MODEL = "llama-3.3-70b-versatile"


def parse_intent(raw_query: str, domain_config: DomainConfig) -> IntentObject:
    """
    Parse a natural language query into a Structured Intent Object.

    Args:
        raw_query:     Natural language search query
        domain_config: Defines fields, valid values, constraint defaults, and LLM prompt

    Returns:
        IntentObject with domain-specific fields extracted and constraint types set

    Raises:
        ValueError: On empty query or unparseable LLM response
    """
    if not raw_query or not raw_query.strip():
        raise ValueError("Query cannot be empty")

    raw_query = raw_query.strip()

    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": domain_config.build_system_prompt()},
                {"role": "user",   "content": f"Parse this {domain_config.domain} query: {raw_query}"},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        raw_json = response.choices[0].message.content.strip()
        raw_json = raw_json.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_json)

    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw_json}")
    except Exception as e:
        raise ValueError(f"LLM API error: {e}")

    fields = {}
    for fd in domain_config.fields:
        raw_field = parsed.get(fd.name, {})
        fields[fd.name] = IntentField(
            value=raw_field.get("value", fd.default_value),
            constraint=raw_field.get("constraint", "none"),
        )

    return IntentObject(
        raw_query=raw_query,
        domain=domain_config.domain,
        fields=fields,
        ambiguity_score=float(parsed.get("ambiguity_score", 0.5)),
    )


# ── TEST ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from engine.domains import get_domain

    config = get_domain('restaurants')

    TEST_QUERIES = [
        "I want a quiet place for a business dinner, good North Indian, Indiranagar, not too loud, parking available",
        "Looking for a rooftop restaurant in Koramangala for a date night, something romantic, mid range",
        "Quick lunch near HSR Layout, South Indian, budget friendly",
        "Something nice for tonight",
        "Good food in Koramangala",
        "Family dinner in Jayanagar, something comfortable for kids, South Indian",
        "Must have parking, North Indian, Indiranagar, business meeting",
    ]

    print(f"\nUniversal Connector — Intent Parser Test")
    print(f"Domain : {config.domain}")
    print(f"Model  : {MODEL}")
    print("=" * 55)

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}] \"{query}\"")
        try:
            intent = parse_intent(query, config)
            print(f"     ambiguity : {intent.ambiguity_score}")
            print(f"     hard      : {intent.hard_constraints()}")
            print(f"     soft      : {intent.soft_constraints()}")
        except Exception as e:
            print(f"     ERROR: {e}")

    print("\nDone.\n")
