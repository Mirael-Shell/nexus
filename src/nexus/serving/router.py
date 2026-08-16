"""A/B routing engine: decides which model variant handles each request.

Strategies:
  - weighted: probabilistic traffic split (e.g. 80/20)
  - shadow: control serves the request, treatment runs alongside silently
"""

from __future__ import annotations

import random

from nexus.core.logging import get_logger

logger = get_logger(__name__)


def assign_variant(traffic_split: float, strategy: str, seed: float | None = None) -> str:
    """Decide which variant (control / treatment) handles a request.

    Args:
        traffic_split: Percentage of traffic to treatment (0-100).
        strategy: "weighted" or "shadow".
        seed: Optional deterministic seed value for reproducibility.

    Returns:
        "control" or "treatment".
    """
    if strategy == "shadow":
        # In shadow mode, control always serves; treatment runs alongside
        return "control"

    # Weighted mode
    threshold = seed % 1.0 * 100 if seed is not None else random.uniform(0, 100)

    variant = "treatment" if threshold < traffic_split else "control"
    logger.debug(
        "Variant assigned",
        variant=variant,
        traffic_split=traffic_split,
        threshold=f"{threshold:.2f}",
    )
    return variant
