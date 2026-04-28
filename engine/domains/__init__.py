"""
Domain registry — maps domain string to DomainConfig.
Adding a new domain: create engine/domains/<domain>.py and register it here.
"""

from engine.domains.base import DomainConfig, FieldDefinition, IntentField, IntentObject
from engine.domains.restaurants import RESTAURANTS_CONFIG

REGISTRY: dict[str, DomainConfig] = {
    'restaurants': RESTAURANTS_CONFIG,
    # 'electronics': ELECTRONICS_CONFIG,
    # 'fashion':     FASHION_CONFIG,
}


def get_domain(domain: str) -> DomainConfig:
    config = REGISTRY.get(domain)
    if not config:
        raise ValueError(
            f"Unknown domain '{domain}'. Available: {list(REGISTRY.keys())}"
        )
    return config
