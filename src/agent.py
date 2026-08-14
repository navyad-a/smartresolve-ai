"""
Core AI Agent for SmartResolve AI.
Integrates LLM-based understanding with schema validation, confidence scoring,
explainability generation, and seamless fallback to deterministic heuristics.
"""

import os
import json
import logging
from typing import List, Tuple, Optional
from dotenv import load_dotenv

from .models import (
    TicketInput,
    TriageOutput,
    CategoryEnum,
    UrgencyEnum,
    TeamEnum,
    BatchSummary
)
from .router import route_ticket, CONFIDENCE_THRESHOLD
from .heuristics import classify_heuristically, extract_keywords

# Load environment variables
load_dotenv()
logger = logging.getLogger("SmartResolveAgent")

SYSTEM_PROMPT = """You are SmartResolve AI, an expert autonomous customer support triage and routing agent.
Your job is to analyze incoming customer support tickets, classify them with precision, score your confidence, determine urgency, and provide clear explainable reasoning.

You must output strictly valid JSON matching this schema:
{
  "category": "Billing & Payments" | "Technical Support" | "Account & Access" | "Security & Fraud" | "Orders & Delivery" | "Product & Features" | "General Inquiry",
  "urgency": "Low" | "Medium" | "High" | "Critical",
  "confidence": <float between 0.00 and 1.00>,
  "reason": "<Detailed 1-2 sentence explanation of why this category and urgency were chosen based on ticket evidence>",
  "recommended_action": "<Specific immediate technical or operational next step for the resolving team>",
  "extracted_keywords": ["keyword1", "keyword2", ...]
}

Classification Guidelines:
1. Urgency:
   - "Critical": Complete service outages, active security compromises, data breaches, or critical operational blockers.
   - "High": Financial errors (double charges), locked accounts, blocked transactions, severe bugs affecting single users.
   - "Medium": Standard feature issues, delayed orders, routine inquiries with standard timelines.
   - "Low": Feature suggestions, general feedback, informational questions.

2. Confidence Calibration:
   - 0.85 to 0.99: Clear, unambiguous requests matching a single distinct department with explicit keywords.
   - 0.70 to 0.84: Valid requests that have minor overlap across departments or partial information.
   - 0.00 to 0.69: Extremely vague, multi-intent conflicting requests, or ambiguous text lacking concrete detail.

Always respond ONLY with the JSON object. Do not include markdown code block backticks if possible, or format as standard json.
"""


class SupportTicketAgent:
    """
    Intelligent Support Ticket Triage Agent.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.confidence_threshold = confidence_threshold
        self._client = None

        if self.api_key:
            try:
                from openai import OpenAI
                # Support custom base url if provided (e.g. Groq, Local Ollama, OpenRouter)
                base_url = os.getenv("OPENAI_BASE_URL", None)
                self._client = OpenAI(api_key=self.api_key, base_url=base_url)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}. Defaulting to heuristic engine.")

    @property
    def is_llm_available(self) -> bool:
        return self._client is not None

    def triage(self, ticket: TicketInput) -> TriageOutput:
        """
        Triages a single support ticket.
        Attempts LLM parsing first. If unavailable, invalid, or upon error, falls back to heuristic engine.
        """
        triage_data = None

        if self.is_llm_available:
            try:
                triage_data = self._triage_with_llm(ticket)
            except Exception as e:
                logger.error(f"LLM triage failed for ticket {ticket.ticket_id}: {e}. Falling back to heuristics.")

        if not triage_data:
            triage_data = self._triage_with_heuristics(ticket)

        # Route through routing engine to evaluate confidence boundary & assign team/SLA
        assigned_team, human_review, sla_hours = route_ticket(
            category=triage_data["category"],
            urgency=triage_data["urgency"],
            confidence=triage_data["confidence"],
            threshold=self.confidence_threshold,
            customer_tier=ticket.customer_tier or "Standard"
        )

        return TriageOutput(
            ticket_id=ticket.ticket_id,
            category=triage_data["category"],
            urgency=triage_data["urgency"],
            confidence=triage_data["confidence"],
            assigned_team=assigned_team,
            human_review_required=human_review,
            reason=triage_data["reason"],
            recommended_action=triage_data["recommended_action"],
            extracted_keywords=triage_data.get("extracted_keywords", []),
            estimated_sla_hours=sla_hours
        )

    def _triage_with_llm(self, ticket: TicketInput) -> Optional[dict]:
        """Calls LLM API with structured prompt and parses JSON."""
        user_content = f"TICKET ID: {ticket.ticket_id}\nSUBJECT: {ticket.subject}\nBODY: {ticket.body}\nCUSTOMER TIER: {ticket.customer_tier}"
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"} if "gpt" in self.model.lower() else None
        )

        raw_content = response.choices[0].message.content.strip()
        # Clean potential markdown backticks
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        raw_content = raw_content.strip()

        parsed = json.loads(raw_content)

        # Map to enums with validation
        category = self._match_category(parsed.get("category", ""))
        urgency = self._match_urgency(parsed.get("urgency", "Medium"))
        confidence = float(parsed.get("confidence", 0.75))
        confidence = max(0.0, min(1.0, confidence))

        keywords = parsed.get("extracted_keywords", [])
        if not keywords:
            keywords = extract_keywords(f"{ticket.subject} {ticket.body}")

        return {
            "category": category,
            "urgency": urgency,
            "confidence": round(confidence, 2),
            "reason": parsed.get("reason", "Classified via LLM triage engine."),
            "recommended_action": parsed.get("recommended_action", "Proceed with standard triage workflow."),
            "extracted_keywords": keywords
        }

    def _triage_with_heuristics(self, ticket: TicketInput) -> dict:
        """Deterministic NLP heuristic fallback classifier."""
        cat, urg, conf, reason, action, kws = classify_heuristically(ticket.subject, ticket.body)
        return {
            "category": cat,
            "urgency": urg,
            "confidence": conf,
            "reason": reason,
            "recommended_action": action,
            "extracted_keywords": kws
        }

    def _match_category(self, cat_str: str) -> CategoryEnum:
        cat_lower = cat_str.lower()
        for member in CategoryEnum:
            if member.value.lower() == cat_lower or member.name.lower() in cat_lower:
                return member
        if "bill" in cat_lower or "pay" in cat_lower:
            return CategoryEnum.BILLING
        if "tech" in cat_lower or "bug" in cat_lower or "api" in cat_lower:
            return CategoryEnum.TECHNICAL
        if "account" in cat_lower or "login" in cat_lower or "pass" in cat_lower:
            return CategoryEnum.ACCOUNT
        if "sec" in cat_lower or "fraud" in cat_lower or "hack" in cat_lower:
            return CategoryEnum.SECURITY
        if "order" in cat_lower or "ship" in cat_lower or "deliver" in cat_lower:
            return CategoryEnum.ORDERS
        if "product" in cat_lower or "feat" in cat_lower:
            return CategoryEnum.PRODUCT
        return CategoryEnum.GENERAL

    def _match_urgency(self, urg_str: str) -> UrgencyEnum:
        urg_lower = urg_str.lower()
        for member in UrgencyEnum:
            if member.value.lower() == urg_lower:
                return member
        if "crit" in urg_lower:
            return UrgencyEnum.CRITICAL
        if "high" in urg_lower:
            return UrgencyEnum.HIGH
        if "low" in urg_lower:
            return UrgencyEnum.LOW
        return UrgencyEnum.MEDIUM

    def triage_batch(self, tickets: List[TicketInput]) -> Tuple[List[TriageOutput], BatchSummary]:
        """Processes a list of tickets and produces detailed outputs & aggregate summary."""
        results: List[TriageOutput] = []
        human_review_count = 0
        critical_count = 0
        total_conf = 0.0

        for t in tickets:
            res = self.triage(t)
            results.append(res)
            if res.human_review_required:
                human_review_count += 1
            if res.urgency == UrgencyEnum.CRITICAL:
                critical_count += 1
            total_conf += res.confidence

        summary = BatchSummary(
            total_tickets=len(tickets),
            auto_routed_count=len(tickets) - human_review_count,
            human_review_count=human_review_count,
            critical_urgency_count=critical_count,
            average_confidence=round(total_conf / len(tickets), 2) if tickets else 0.0
        )

        return results, summary
