"""
UNIVERSAL CONNECTOR — Domain Configuration Base
Defines the types that make the engine domain-agnostic.

A DomainConfig describes everything domain-specific:
  - what fields exist in an intent for this domain
  - how to filter sources by hard constraints (SQL)
  - how to score sources against soft constraints
  - how trust edges and interactions are stored for this domain

Adding a new domain = writing a new DomainConfig instance.
The engine (intent_parser, matcher) never hardcodes domain knowledge.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import json


# ── INTENT TYPES ──────────────────────────────────────────────────────────────

@dataclass
class IntentField:
    value: Any
    constraint: str  # 'hard' | 'soft' | 'none'


@dataclass
class IntentObject:
    raw_query:       str
    domain:          str
    fields:          dict[str, IntentField]
    ambiguity_score: float = 0.0

    def hard_constraints(self) -> dict:
        return {
            k: v.value for k, v in self.fields.items()
            if v.constraint == 'hard' and v.value not in [None, [], '']
        }

    def soft_constraints(self) -> dict:
        return {
            k: v.value for k, v in self.fields.items()
            if v.constraint == 'soft' and v.value not in [None, [], '']
        }

    def get(self, name: str) -> Optional[IntentField]:
        return self.fields.get(name)

    def to_dict(self) -> dict:
        return {
            'raw_query':       self.raw_query,
            'domain':          self.domain,
            'ambiguity_score': self.ambiguity_score,
            'fields': {
                k: {'value': v.value, 'constraint': v.constraint}
                for k, v in self.fields.items()
            },
        }


# ── DOMAIN CONFIGURATION TYPES ───────────────────────────────────────────────

@dataclass
class FieldDefinition:
    name:               str
    field_type:         str          # 'list' | 'string' | 'boolean' | 'integer' | 'float'
    valid_values:       list         # empty list = any value accepted
    default_constraint: str          # 'hard' | 'soft' | 'none'
    default_value:      Any          # None or []
    db_column:          Optional[str] # None = not a filterable/scorable DB column
    filter_type:        str          # 'exact' | 'array_overlap' | 'boolean' | 'none'
    score_weight:       float        # 0.0 = not scored (filter-only or metadata)
    relaxable:          bool         # relax this hard constraint on zero-result fallback?
    similarity_map:     dict         # {intent_val: {source_val: score}} for fuzzy matching
    prompt_hint:        str          # extra LLM guidance injected into the system prompt


@dataclass
class DomainConfig:
    domain:                str
    source_table:          str        # e.g. 'restaurants', 'products'
    source_fk_column:      str        # FK column in interactions table, e.g. 'restaurant_id'
    trust_received_column: str        # column in users table, e.g. 'trust_received_restaurants'
    select_columns:        list[str]  # columns to SELECT from source_table
    fields:                list[FieldDefinition]
    max_trust_hops:        int = 3    # per-domain trust traversal depth cap

    # ── field accessors ───────────────────────────────────────────────────────

    def get_field(self, name: str) -> Optional[FieldDefinition]:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def scored_fields(self) -> list[FieldDefinition]:
        """Fields that contribute to intent match score."""
        return [f for f in self.fields if f.score_weight > 0 and f.db_column]

    def filterable_fields(self) -> list[FieldDefinition]:
        """Fields that can be used as SQL WHERE filters."""
        return [f for f in self.fields if f.filter_type != 'none' and f.db_column]

    def relaxable_fields(self) -> list[FieldDefinition]:
        """Hard constraints that can be relaxed on zero-result fallback."""
        return [f for f in self.fields if f.relaxable]

    # ── system prompt generation ──────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        """
        Generate the LLM system prompt from field definitions.
        No domain-specific knowledge lives in the parser — it comes from here.
        """
        lines = [
            f'You are an intent parser for a {self.domain} discovery system.',
            '',
            'Your job is to extract structured information from a natural language search query.',
            '',
            'You MUST respond with ONLY valid JSON. No explanation, no markdown, no backticks.',
            '',
            'Extract these fields:',
        ]

        for fd in self.fields:
            if fd.field_type == 'list':
                vals = ', '.join(f'"{v}"' for v in fd.valid_values) if fd.valid_values else 'any string'
                line = f'- {fd.name}: list of strings. Valid values: {vals}. Empty list if not mentioned.'
            elif fd.field_type == 'string':
                vals = ', '.join(f'"{v}"' for v in fd.valid_values) if fd.valid_values else 'any string'
                line = f'- {fd.name}: string. Valid values: {vals}. Null if not mentioned.'
            elif fd.field_type == 'boolean':
                line = f'- {fd.name}: boolean. True only if explicitly required. Null if not mentioned.'
            elif fd.field_type == 'integer':
                line = f'- {fd.name}: integer. Null if not mentioned.'
            else:
                line = f'- {fd.name}: value or null.'

            if fd.prompt_hint:
                line += f'\n  {fd.prompt_hint}'
            lines.append(line)

        hard_fields = [f.name for f in self.fields if f.default_constraint == 'hard']
        soft_fields = [f.name for f in self.fields if f.default_constraint == 'soft']

        lines += [
            '',
            'For EACH field also set constraint type:',
            '- "hard": user explicitly requires this — violation means exclude entirely.',
            f'  Typical hard fields for this domain: {", ".join(hard_fields)}',
            '  Use "hard" sparingly — only when the user clearly cannot accept alternatives.',
            '- "soft": user prefers this but would accept alternatives.',
            f'  Typical soft fields for this domain: {", ".join(soft_fields)}',
            '- "none": field was not mentioned.',
            '',
            '- ambiguity_score: float 0.0 to 1.0. '
            'How vague is the query? 0.0 = very specific, 1.0 = completely vague.',
            '',
            'Respond with this exact JSON structure:',
        ]

        schema: dict[str, Any] = {}
        for fd in self.fields:
            if fd.field_type == 'list':
                schema[fd.name] = {'value': [], 'constraint': 'hard|soft|none'}
            elif fd.field_type == 'boolean':
                schema[fd.name] = {'value': 'true/false/null', 'constraint': 'hard|soft|none'}
            else:
                schema[fd.name] = {'value': '...', 'constraint': 'hard|soft|none'}
        schema['ambiguity_score'] = 0.0

        lines.append(json.dumps(schema, indent=2))
        return '\n'.join(lines)
