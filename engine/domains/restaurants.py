"""
UNIVERSAL CONNECTOR — Restaurants Domain Config
Phase 1 domain. All restaurant-specific knowledge lives here.

To add a new domain, create a similar file and register it in __init__.py.
"""

from engine.domains.base import DomainConfig, FieldDefinition

RESTAURANTS_CONFIG = DomainConfig(
    domain='restaurants',
    source_table='restaurants',
    source_fk_column='restaurant_id',
    trust_received_column='trust_received_restaurants',
    select_columns=[
        'id', 'name', 'area', 'cuisine', 'vibe', 'occasion',
        'price_range', 'noise_level', 'seating_type', 'parking',
        'tags', 'avg_outcome_score', 'total_visits', 'trust_citations',
    ],
    fields=[
        FieldDefinition(
            name='cuisine',
            field_type='list',
            valid_values=[
                'North Indian', 'South Indian', 'Chinese', 'Italian',
                'Continental', 'Cafe', 'Biryani', 'Street Food',
                'Pan Asian', 'Mediterranean', 'Mexican',
            ],
            default_constraint='hard',
            default_value=[],
            db_column='cuisine',
            filter_type='array_overlap',
            score_weight=0.20,
            relaxable=True,
            similarity_map={},
            prompt_hint='',
        ),
        FieldDefinition(
            name='area',
            field_type='string',
            valid_values=['Koramangala', 'Indiranagar', 'HSR Layout', 'Jayanagar'],
            default_constraint='hard',
            default_value=None,
            db_column='area',
            filter_type='exact',
            score_weight=0.10,
            relaxable=False,  # never drop area — it's the user's location anchor
            similarity_map={},
            prompt_hint='',
        ),
        FieldDefinition(
            name='occasion',
            field_type='list',
            valid_values=[
                'casual', 'date-night', 'business', 'family',
                'quick-lunch', 'celebration', 'friends-hangout',
            ],
            default_constraint='soft',
            default_value=[],
            db_column='occasion',
            filter_type='array_overlap',
            score_weight=0.35,
            relaxable=True,
            similarity_map={
                'business':        {'business': 1.0, 'casual': 0.4, 'celebration': 0.3},
                'date-night':      {'date-night': 1.0, 'romantic': 0.8, 'casual': 0.3, 'celebration': 0.5},
                'family':          {'family': 1.0, 'casual': 0.4, 'celebration': 0.5},
                'casual':          {'casual': 1.0, 'friends-hangout': 0.8, 'quick-lunch': 0.6, 'family': 0.4},
                'celebration':     {'celebration': 1.0, 'date-night': 0.6, 'family': 0.5, 'casual': 0.3},
                'friends-hangout': {'friends-hangout': 1.0, 'casual': 0.8, 'celebration': 0.4},
                'quick-lunch':     {'quick-lunch': 1.0, 'casual': 0.6},
            },
            prompt_hint=(
                'CRITICAL RULE: occasion should almost always be "soft" not "hard". '
                'Restaurants may not explicitly tag their occasion types. '
                'Use occasion to improve ranking only, not to exclude restaurants.'
            ),
        ),
        FieldDefinition(
            name='vibe',
            field_type='list',
            valid_values=[
                'cozy', 'lively', 'rooftop', 'quiet', 'romantic',
                'family-friendly', 'trendy', 'rustic', 'minimalist',
            ],
            default_constraint='soft',
            default_value=[],
            db_column='vibe',
            filter_type='array_overlap',
            score_weight=0.30,
            relaxable=True,
            similarity_map={},
            prompt_hint=(
                'IMPORTANT: vibe is almost always SOFT. '
                'Only set "hard" if the user says "must be rooftop" or "only outdoor seating".'
            ),
        ),
        FieldDefinition(
            name='price_range',
            field_type='string',
            valid_values=['budget', 'mid', 'premium'],
            default_constraint='soft',
            default_value=None,
            db_column='price_range',
            filter_type='exact',
            score_weight=0.05,
            relaxable=True,
            similarity_map={},
            prompt_hint='',
        ),
        FieldDefinition(
            name='noise_level',
            field_type='string',
            valid_values=['quiet', 'moderate', 'loud'],
            default_constraint='soft',
            default_value=None,
            db_column='noise_level',
            filter_type='exact',
            score_weight=0.05,
            relaxable=True,
            similarity_map={},
            prompt_hint=(
                'Phrases like "not too loud", "quiet place", "peaceful" map to noise_level="quiet". '
                'Do NOT also set vibe="quiet" — noise_level captures it already.'
            ),
        ),
        FieldDefinition(
            name='parking',
            field_type='boolean',
            valid_values=[],
            default_constraint='hard',
            default_value=None,
            db_column='parking',
            filter_type='boolean',
            score_weight=0.0,   # filter-only, not scored
            relaxable=True,
            similarity_map={},
            prompt_hint='True only if parking is explicitly needed.',
        ),
        FieldDefinition(
            name='group_size',
            field_type='integer',
            valid_values=[],
            default_constraint='none',
            default_value=None,
            db_column=None,     # no direct DB column — captured for future use
            filter_type='none',
            score_weight=0.0,
            relaxable=False,
            similarity_map={},
            prompt_hint='',
        ),
        FieldDefinition(
            name='seating_type',
            field_type='list',
            valid_values=['indoor', 'outdoor', 'rooftop'],
            default_constraint='hard',
            default_value=[],
            db_column='seating_type',
            filter_type='array_overlap',
            score_weight=0.0,   # filter-only, not scored
            relaxable=True,
            similarity_map={},
            prompt_hint='',
        ),
    ],
)
