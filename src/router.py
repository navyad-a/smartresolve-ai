"""
Deterministic Routing & SLA Engine for SmartResolve AI.
Handles team assignment mapping, SLA calculation, and escalation rules.
"""

from typing import Tuple
from .models import CategoryEnum, UrgencyEnum, TeamEnum


# Category to Team Mapping Dictionary
CATEGORY_TEAM_MAP = {
    CategoryEnum.BILLING: TeamEnum.BILLING_TEAM,
    CategoryEnum.TECHNICAL: TeamEnum.TECH_SUPPORT,
    CategoryEnum.ACCOUNT: TeamEnum.ACCOUNT_SECURITY,
    CategoryEnum.SECURITY: TeamEnum.SECURITY_OPS,
    CategoryEnum.ORDERS: TeamEnum.LOGISTICS,
    CategoryEnum.PRODUCT: TeamEnum.PRODUCT_MGMT,
    CategoryEnum.GENERAL: TeamEnum.CUSTOMER_CARE,
}

# SLA Resolution Targets in Hours based on Urgency
SLA_HOURS_MAP = {
    UrgencyEnum.CRITICAL: 2,
    UrgencyEnum.HIGH: 6,
    UrgencyEnum.MEDIUM: 24,
    UrgencyEnum.LOW: 48,
}

CONFIDENCE_THRESHOLD = 0.75


def route_ticket(
    category: CategoryEnum,
    urgency: UrgencyEnum,
    confidence: float,
    threshold: float = CONFIDENCE_THRESHOLD,
    customer_tier: str = "Standard"
) -> Tuple[TeamEnum, bool, int]:
    """
    Determines final routing team, human-review flag, and SLA hours.

    Rules:
    1. If confidence < threshold (0.75), human review is REQUIRED, and the ticket is sent
       to the Human Review Queue (Uncertain Triage), while preserving category recommendation.
    2. If category is Security & Fraud and urgency is Critical/High, SLA is expedited.
    3. Enterprise tier customers get expedited SLA (50% reduction).
    """
    is_unsure = confidence < threshold

    if is_unsure:
        target_team = TeamEnum.HUMAN_TRIAGE
        human_review_required = True
    else:
        target_team = CATEGORY_TEAM_MAP.get(category, TeamEnum.CUSTOMER_CARE)
        human_review_required = False

    # Base SLA computation
    base_sla = SLA_HOURS_MAP.get(urgency, 24)

    # Enterprise adjustment
    if customer_tier.lower() == "enterprise":
        base_sla = max(1, base_sla // 2)

    return target_team, human_review_required, base_sla
