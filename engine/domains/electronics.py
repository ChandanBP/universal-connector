"""
UNIVERSAL CONNECTOR — Electronics Domain Config
Phase 2 domain. Proves the "Universal" claim.

max_trust_hops=2: electronics purchases are higher-stakes than restaurant visits,
so we restrict trust traversal to direct + one-hop network only.
"""

from engine.domains.base import DomainConfig, FieldDefinition

ELECTRONICS_CONFIG = DomainConfig(
    domain='electronics',
    source_table='products',
    source_fk_column='product_id',
    trust_received_column='trust_received_electronics',
    max_trust_hops=2,
    select_columns=[
        'id', 'name', 'brand', 'category', 'use_case', 'price_range',
        'condition', 'connectivity', 'battery_life', 'portability',
        'tags', 'avg_outcome_score', 'total_visits', 'trust_citations',
    ],
    fields=[
        FieldDefinition(
            name='category',
            field_type='string',
            valid_values=[
                'phone', 'laptop', 'tablet', 'headphones', 'smartwatch',
                'camera', 'tv', 'speaker', 'monitor', 'keyboard',
            ],
            default_constraint='hard',
            default_value=None,
            db_column='category',
            filter_type='exact',
            score_weight=0.30,
            relaxable=False,   # user asking for a laptop does not want a phone
            similarity_map={},
            prompt_hint=(
                'category is almost always "hard". '
                'If the user says "headphones", do not include speakers or monitors.'
            ),
        ),
        FieldDefinition(
            name='brand',
            field_type='list',
            valid_values=[
                'Apple', 'Samsung', 'Sony', 'Bose', 'Dell', 'HP', 'Lenovo',
                'Asus', 'LG', 'OnePlus', 'Google', 'Microsoft', 'JBL',
                'Jabra', 'Sennheiser', 'Canon', 'Nikon', 'Logitech',
            ],
            default_constraint='soft',
            default_value=[],
            db_column='brand',
            filter_type='array_overlap',
            score_weight=0.15,
            relaxable=True,
            similarity_map={},
            prompt_hint=(
                'brand is almost always "soft". '
                'Only set "hard" if the user explicitly says "only Apple" or "must be Sony".'
            ),
        ),
        FieldDefinition(
            name='use_case',
            field_type='list',
            valid_values=[
                'work', 'gaming', 'travel', 'fitness', 'content-creation',
                'casual-use', 'professional', 'student', 'home-office',
            ],
            default_constraint='soft',
            default_value=[],
            db_column='use_case',
            filter_type='array_overlap',
            score_weight=0.25,
            relaxable=True,
            similarity_map={
                'work':             {'work': 1.0, 'home-office': 0.8, 'professional': 0.7, 'student': 0.4},
                'gaming':           {'gaming': 1.0, 'casual-use': 0.4, 'content-creation': 0.3},
                'travel':           {'travel': 1.0, 'casual-use': 0.5, 'fitness': 0.3},
                'fitness':          {'fitness': 1.0, 'travel': 0.4, 'casual-use': 0.3},
                'content-creation': {'content-creation': 1.0, 'professional': 0.6, 'work': 0.4},
                'casual-use':       {'casual-use': 1.0, 'student': 0.6, 'travel': 0.4},
                'professional':     {'professional': 1.0, 'work': 0.8, 'content-creation': 0.5},
                'student':          {'student': 1.0, 'casual-use': 0.6, 'work': 0.4},
                'home-office':      {'home-office': 1.0, 'work': 0.9, 'professional': 0.5},
            },
            prompt_hint=(
                'use_case should almost always be "soft". '
                'Phrases like "for my studies" → student, "for editing videos" → content-creation, '
                '"for gym" → fitness, "work from home" → home-office.'
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
            score_weight=0.15,
            relaxable=True,
            similarity_map={},
            prompt_hint=(
                'Map budget signals: "affordable", "cheap", "low-cost" → budget; '
                '"mid-range", "decent" → mid; '
                '"flagship", "high-end", "best" → premium.'
            ),
        ),
        FieldDefinition(
            name='condition',
            field_type='string',
            valid_values=['new', 'refurbished'],
            default_constraint='hard',
            default_value='new',
            db_column='condition',
            filter_type='exact',
            score_weight=0.05,
            relaxable=True,   # relax if zero results; user may not mind refurbished
            similarity_map={},
            prompt_hint='Default to "new" unless user explicitly says "refurbished" or "second-hand".',
        ),
        FieldDefinition(
            name='battery_life',
            field_type='string',
            valid_values=['excellent', 'good', 'average', 'na'],
            default_constraint='soft',
            default_value=None,
            db_column='battery_life',
            filter_type='exact',
            score_weight=0.10,
            relaxable=True,
            similarity_map={},
            prompt_hint=(
                'Phrases like "long battery", "all-day battery" → excellent; '
                '"decent battery" → good. '
                'For desktops and monitors use "na". Only set if battery is explicitly mentioned.'
            ),
        ),
        FieldDefinition(
            name='portability',
            field_type='string',
            valid_values=['highly-portable', 'portable', 'desktop'],
            default_constraint='soft',
            default_value=None,
            db_column='portability',
            filter_type='exact',
            score_weight=0.0,   # filter-only when mentioned
            relaxable=True,
            similarity_map={},
            prompt_hint=(
                '"lightweight", "compact", "carry around" → highly-portable; '
                '"for home use only", "stationary" → desktop. '
                'Only set if portability is explicitly mentioned.'
            ),
        ),
    ],
)
