"""
Unit and Integration Tests for SmartResolve AI.
Tests classification accuracy, confidence boundary gating, edge cases, and routing rules.
"""

import pytest
from src.models import TicketInput, CategoryEnum, UrgencyEnum, TeamEnum
from src.agent import SupportTicketAgent
from src.router import route_ticket, CONFIDENCE_THRESHOLD


@pytest.fixture
def agent():
    """Fixture providing SupportTicketAgent instance with standard 0.75 threshold."""
    return SupportTicketAgent(confidence_threshold=0.75)


def test_billing_classification_high_confidence(agent):
    """Verifies that billing tickets are categorized correctly and auto-routed."""
    ticket = TicketInput(
        ticket_id="T-TEST-01",
        subject="Duplicate subscription charge on invoice",
        body="I was charged $49 twice on my Mastercard for this month. Please issue a refund.",
        customer_tier="Standard"
    )
    result = agent.triage(ticket)

    assert result.category == CategoryEnum.BILLING
    assert result.assigned_team == TeamEnum.BILLING_TEAM
    assert result.confidence >= CONFIDENCE_THRESHOLD
    assert result.human_review_required is False
    assert result.urgency in [UrgencyEnum.HIGH, UrgencyEnum.MEDIUM]
    assert len(result.reason) > 10


def test_critical_security_escalation(agent):
    """Verifies that security incidents are assigned Critical/High urgency and SOC team."""
    ticket = TicketInput(
        ticket_id="T-TEST-02",
        subject="Unauthorized root access and data breach detected",
        body="We detected suspicious unauthorized API logins from unknown IP and key leakage.",
        customer_tier="Enterprise"
    )
    result = agent.triage(ticket)

    assert result.category == CategoryEnum.SECURITY
    assert result.assigned_team == TeamEnum.SECURITY_OPS
    assert result.urgency == UrgencyEnum.CRITICAL
    assert result.estimated_sla_hours <= 2


def test_technical_outage(agent):
    """Verifies server crash and API outage routing to Technical Support."""
    ticket = TicketInput(
        ticket_id="T-TEST-03",
        subject="Production server returning 500 error code",
        body="Our users cannot query endpoints due to 500 internal server timeout and crash.",
        customer_tier="Enterprise"
    )
    result = agent.triage(ticket)

    assert result.category == CategoryEnum.TECHNICAL
    assert result.assigned_team == TeamEnum.TECH_SUPPORT
    assert result.urgency in [UrgencyEnum.CRITICAL, UrgencyEnum.HIGH]


def test_ambiguous_ticket_triggers_human_review(agent):
    """Verifies that vague/short tickets trigger the <0.75 human review boundary."""
    ticket = TicketInput(
        ticket_id="T-TEST-04",
        subject="Help",
        body="Please fix this immediately.",
        customer_tier="Standard"
    )
    result = agent.triage(ticket)

    assert result.confidence < CONFIDENCE_THRESHOLD
    assert result.human_review_required is True
    assert result.assigned_team == TeamEnum.HUMAN_TRIAGE


def test_batch_triage(agent):
    """Verifies batch processing of multiple tickets and summary calculations."""
    tickets = [
        TicketInput(ticket_id="T1", subject="Refund needed for duplicate payment", body="Charged twice.", customer_tier="Standard"),
        TicketInput(ticket_id="T2", subject="Server crashed with 500 error", body="API timeout.", customer_tier="Enterprise"),
        TicketInput(ticket_id="T3", subject="Help", body="Something broke.", customer_tier="Standard")
    ]
    results, summary = agent.triage_batch(tickets)

    assert len(results) == 3
    assert summary.total_tickets == 3
    assert summary.human_review_count >= 1  # T3 should trigger review
    assert summary.auto_routed_count >= 1


def test_routing_engine_threshold_override():
    """Verifies router logic when overriding confidence threshold."""
    # When confidence is 0.70 and threshold is 0.75 -> Human review
    team, review, sla = route_ticket(CategoryEnum.BILLING, UrgencyEnum.HIGH, confidence=0.70, threshold=0.75)
    assert review is True
    assert team == TeamEnum.HUMAN_TRIAGE

    # When confidence is 0.70 and threshold is 0.60 -> Auto-routed
    team, review, sla = route_ticket(CategoryEnum.BILLING, UrgencyEnum.HIGH, confidence=0.70, threshold=0.60)
    assert review is False
    assert team == TeamEnum.BILLING_TEAM
