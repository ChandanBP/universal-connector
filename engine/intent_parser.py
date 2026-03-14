"""
UNIVERSAL CONNECTOR — Intent Parser
Phase 1: Restaurants Domain

Converts natural language query into
a Structured Intent Object using Groq + Llama 3.1

Usage:
  from engine.intent_parser import parse_intent
  intent = parse_intent("quiet North Indian in Indiranagar for business dinner")
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── GROQ CLIENT ───────────────────────────────────────────────────────────────
try:
    from groq import Groq
    _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except ImportError:
    raise ImportError("Run: pip install groq")

MODEL = "llama-3.3-70b-versatile"

# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class IntentField:
    """A single field in the intent object with constraint type."""
    value: any
    constraint: str  # 'hard' | 'soft' | 'none'

@dataclass
class IntentObject:
    """
    Structured representation of what a user wants.
    Hard constraints = must match or restaurant is excluded.
    Soft constraints = nice to have, affects ranking score.
    """
    raw_query:       str
    cuisine:         IntentField = field(default_factory=lambda: IntentField([], "none"))
    area:            IntentField = field(default_factory=lambda: IntentField(None, "none"))
    occasion:        IntentField = field(default_factory=lambda: IntentField([], "none"))
    vibe:            IntentField = field(default_factory=lambda: IntentField([], "none"))
    price_range:     IntentField = field(default_factory=lambda: IntentField(None, "none"))
    noise_level:     IntentField = field(default_factory=lambda: IntentField(None, "none"))
    parking:         IntentField = field(default_factory=lambda: IntentField(None, "none"))
    group_size:      IntentField = field(default_factory=lambda: IntentField(None, "none"))
    seating_type:    IntentField = field(default_factory=lambda: IntentField([], "none"))
    ambiguity_score: float = 0.0   # 0.0 = very clear, 1.0 = very vague

    def hard_constraints(self) -> dict:
        """Return only hard constraint fields with values."""
        result = {}
        for fname in ["cuisine", "area", "occasion", "vibe",
                      "price_range", "noise_level", "parking",
                      "group_size", "seating_type"]:
            f = getattr(self, fname)
            if f.constraint == "hard" and f.value not in [None, [], ""]:
                result[fname] = f.value
        return result

    def soft_constraints(self) -> dict:
        """Return only soft constraint fields with values."""
        result = {}
        for fname in ["cuisine", "area", "occasion", "vibe",
                      "price_range", "noise_level", "parking",
                      "group_size", "seating_type"]:
            f = getattr(self, fname)
            if f.constraint == "soft" and f.value not in [None, [], ""]:
                result[fname] = f.value
        return result

    def to_dict(self) -> dict:
        return {
            "raw_query":       self.raw_query,
            "ambiguity_score": self.ambiguity_score,
            "fields": {
                fname: {"value": getattr(self, fname).value,
                        "constraint": getattr(self, fname).constraint}
                for fname in ["cuisine", "area", "occasion", "vibe",
                              "price_range", "noise_level", "parking",
                              "group_size", "seating_type"]
            }
        }


# ── PROMPT ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intent parser for a restaurant discovery system in Bangalore, India.

Your job is to extract structured information from a natural language restaurant search query.

You MUST respond with ONLY valid JSON. No explanation, no markdown, no backticks.

Extract these fields:
- cuisine: list of strings. Valid values: "North Indian", "South Indian", "Chinese", "Italian", "Continental", "Cafe", "Biryani", "Street Food", "Pan Asian", "Mediterranean", "Mexican". Empty list if not mentioned.
- area: string. Valid areas: "Koramangala", "Indiranagar", "HSR Layout", "Jayanagar". Null if not mentioned.
- occasion: list of strings. Valid values: "casual", "date-night", "business", "family", "quick-lunch", "celebration", "friends-hangout". Empty list if not mentioned.
- vibe: list of strings. Valid values: "cozy", "lively", "rooftop", "quiet", "romantic", "family-friendly", "trendy", "rustic", "minimalist". Empty list if not mentioned.
  IMPORTANT: vibe is almost always a SOFT preference, not hard. Only set vibe constraint to "hard" if user says something like "must be rooftop" or "only outdoor".
- price_range: string. Valid values: "budget", "mid", "premium". Null if not mentioned.
- noise_level: string. Valid values: "quiet", "moderate", "loud". Null if not mentioned.
  IMPORTANT: phrases like "not too loud", "quiet place", "peaceful" map to noise_level="quiet".
  Do NOT also set vibe="quiet" for these phrases — noise_level captures it already.
- parking: boolean. True if parking explicitly needed. Null if not mentioned.
- group_size: integer. Null if not mentioned.
- seating_type: list of strings. Valid values: "indoor", "outdoor", "rooftop". Empty list if not mentioned.

For EACH field also set constraint type:
- "hard": user explicitly requires this — violation means exclude the restaurant entirely.
  Use "hard" for: cuisine, area, parking (when mentioned), seating_type (when explicitly required).
  Use "hard" sparingly — only when user clearly cannot accept alternatives.
- "soft": user prefers this but would accept alternatives.
  Use "soft" for: vibe, price_range, noise_level, occasion (these improve ranking but dont exclude).
- "none": field was not mentioned.

CRITICAL RULE: occasion should almost always be "soft" not "hard".
Restaurants may not explicitly tag their occasion types.
Use occasion to improve ranking only, not to exclude restaurants.

Also set:
- ambiguity_score: float 0.0 to 1.0. How vague is the query? 0.0 = very specific, 1.0 = completely vague.

Respond with this exact JSON structure:
{
  "cuisine":      {"value": [...], "constraint": "hard|soft|none"},
  "area":         {"value": "...", "constraint": "hard|soft|none"},
  "occasion":     {"value": [...], "constraint": "hard|soft|none"},
  "vibe":         {"value": [...], "constraint": "hard|soft|none"},
  "price_range":  {"value": "...", "constraint": "hard|soft|none"},
  "noise_level":  {"value": "...", "constraint": "hard|soft|none"},
  "parking":      {"value": true/false/null, "constraint": "hard|soft|none"},
  "group_size":   {"value": null, "constraint": "none"},
  "seating_type": {"value": [...], "constraint": "hard|soft|none"},
  "ambiguity_score": 0.0
}"""


# ── PARSER ────────────────────────────────────────────────────────────────────

def parse_intent(raw_query: str) -> IntentObject:
    """
    Parse a natural language restaurant query into a Structured Intent Object.

    Args:
        raw_query: Natural language restaurant search query

    Returns:
        IntentObject with all fields extracted and constraint types set

    Raises:
        ValueError: If Groq returns unparseable response
    """
    if not raw_query or not raw_query.strip():
        raise ValueError("Query cannot be empty")

    raw_query = raw_query.strip()

    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Parse this restaurant query: {raw_query}"}
            ],
            temperature=0.1,      # Low temp for consistent structured output
            max_tokens=500,
        )

        raw_json = response.choices[0].message.content.strip()

        # Clean up any accidental markdown fences
        raw_json = raw_json.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw_json)

    except json.JSONDecodeError as e:
        raise ValueError(f"Groq returned invalid JSON: {e}\nRaw: {raw_json}")
    except Exception as e:
        raise ValueError(f"Groq API error: {e}")

    # ── Build IntentObject from parsed JSON ───────────────────────────────────
    def field(key, default):
        f = parsed.get(key, {})
        return IntentField(
            value=f.get("value", default),
            constraint=f.get("constraint", "none")
        )

    intent = IntentObject(
        raw_query=raw_query,
        cuisine=field("cuisine", []),
        area=field("area", None),
        occasion=field("occasion", []),
        vibe=field("vibe", []),
        price_range=field("price_range", None),
        noise_level=field("noise_level", None),
        parking=field("parking", None),
        group_size=field("group_size", None),
        seating_type=field("seating_type", []),
        ambiguity_score=float(parsed.get("ambiguity_score", 0.5)),
    )

    return intent


# ── TEST ──────────────────────────────────────────────────────────────────────

TEST_QUERIES = [
    # Clear, specific queries
    "I want a quiet place for a business dinner, good North Indian, Indiranagar, not too loud, parking available",
    "Looking for a rooftop restaurant in Koramangala for a date night, something romantic, mid range",
    "Quick lunch near HSR Layout, South Indian, budget friendly",

    # Vague queries (tests ambiguity score)
    "Something nice for tonight",
    "Good food in Koramangala",

    # Family / occasion specific
    "Family dinner in Jayanagar, something comfortable for kids, South Indian",

    # Hard constraint test
    "Must have parking, North Indian, Indiranagar, business meeting",
]

if __name__ == "__main__":
    print("\n🧠 Universal Connector — Intent Parser Test")
    print("=" * 55)
    print(f"Model: {MODEL}")
    print("=" * 55)

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}] Query: \"{query}\"")
        try:
            intent = parse_intent(query)
            print(f"     Ambiguity score : {intent.ambiguity_score}")
            print(f"     Hard constraints: {intent.hard_constraints()}")
            print(f"     Soft constraints: {intent.soft_constraints()}")
        except Exception as e:
            print(f"     ❌ Error: {e}")

    print("\n✅ Intent parser test complete\n")