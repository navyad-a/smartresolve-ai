"""
SmartResolve AI package.
Intelligent Support Ticket Triage and Routing Agent.
"""

from .models import TicketInput, TriageOutput, CategoryEnum, UrgencyEnum, TeamEnum
from .agent import SupportTicketAgent
from .router import route_ticket

__all__ = [
    "TicketInput",
    "TriageOutput",
    "CategoryEnum",
    "UrgencyEnum",
    "TeamEnum",
    "SupportTicketAgent",
    "route_ticket"
]
