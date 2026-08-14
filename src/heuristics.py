"""
Rule-based NLP & Heuristic Classifier for SmartResolve AI.
Provides deterministic scoring, keyword extraction, and serves as an offline fallback engine.
"""

import re
from typing import Dict, List, Tuple
from .models import CategoryEnum, UrgencyEnum


# Keyword weights for category detection
CATEGORY_KEYWORDS: Dict[CategoryEnum, List[str]] = {
    CategoryEnum.BILLING: [
        "charge", "charged", "invoice", "refund", "receipt", "payment", "subscription",
        "double charged", "overcharged", "card", "bank", "credit", "billing", "pricing",
        "renew", "renewal", "cancel subscription", "deducted", "wire transfer", "money",
        "vat", "tax invoice", "upi", "debited"
    ],
    CategoryEnum.TECHNICAL: [
        "api", "server", "crash", "error", "bug", "timeout", "500", "502", "503", "404",
        "down", "outage", "database", "sql", "exception", "broken", "endpoint", "sdk",
        "latency", "slow", "stack trace", "fail", "failed", "gateway", "integration",
        "postgres", "connection pool", "webhook", "webhooks"
    ],
    CategoryEnum.ACCOUNT: [
        "password", "login", "locked", "mfa", "2fa", "reset password", "sign in", "sso",
        "authenticator", "verification", "access", "email change", "profile", "account access",
        "cannot log in", "cant login", "credentials", "otp", "code expired"
    ],
    CategoryEnum.SECURITY: [
        "hacked", "breach", "compromised", "unauthorized", "suspicious", "fraud", "phishing",
        "security", "stolen", "vulnerability", "malware", "leak", "ransomware", "data leak",
        "unknown device", "hijacked", "illegal access", "injection", "sql injection"
    ],
    CategoryEnum.ORDERS: [
        "order", "shipment", "shipping", "delivery", "track", "tracking", "package", "transit",
        "delayed", "carrier", "delivered", "courier", "missing item", "damaged package",
        "dispatch", "return item", "address change", "parcel"
    ],
    CategoryEnum.PRODUCT: [
        "feature", "feature request", "feedback", "suggestion", "dark mode", "ui", "ux",
        "enhancement", "roadmap", "export feature", "integration request", "button", "design",
        "tutorial", "documentation", "how to", "shortcuts", "hotkeys"
    ],
    CategoryEnum.GENERAL: [
        "hello", "hi", "help", "information", "question", "inquiry", "talk to human",
        "representative", "contact", "office", "timing", "pricing info", "assistance",
        "guidance", "sales"
    ]
}

# Urgency indicators
CRITICAL_INDICATORS = [
    "production down", "outage", "system down", "all users affected", "data breach",
    "ransomware", "hacked", "security alert", "cannot process transactions", "zero day",
    "completely blocked", "emergency", "vulnerability", "leak", "pool exhaustion"
]

HIGH_INDICATORS = [
    "urgent", "asap", "locked out", "charged twice", "cannot access", "deadline",
    "major bug", "payment failed", "unauthorized login", "high priority", "overcharged",
    "500", "crash", "timeout", "broken", "server", "immediately", "compromised", "production"
]

LOW_INDICATORS = [
    "when you have time", "not urgent", "minor suggestion", "feedback",
    "just curious", "feature request", "nice to have", "roadmap", "dark mode"
]


def extract_keywords(text: str) -> List[str]:
    """Extract recognized domain keywords from text."""
    text_lower = text.lower()
    found = set()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                found.add(kw)
    return sorted(list(found))


def classify_heuristically(subject: str, body: str) -> Tuple[CategoryEnum, UrgencyEnum, float, str, str, List[str]]:
    """
    Classifies a ticket using rule-based scoring.
    Returns: (category, urgency, confidence, reason, recommended_action, extracted_keywords)
    """
    full_text = f"{subject} {body}".lower().strip()
    extracted_kws = extract_keywords(full_text)
    word_count = len(full_text.split())

    # Score categories
    category_scores: Dict[CategoryEnum, float] = {cat: 0.0 for cat in CategoryEnum}

    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            # Subject matches have higher weight (2.5x) than body matches (1.0x)
            if re.search(r'\b' + re.escape(kw) + r'\b', subject.lower()):
                category_scores[cat] += 2.5
            if re.search(r'\b' + re.escape(kw) + r'\b', body.lower()):
                category_scores[cat] += 1.0

    # Sort categories by score
    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_score = sorted_cats[0]
    runner_up_cat, runner_up_score = sorted_cats[1]

    # Ambiguity detection:
    # 1. Extremely brief message (word count < 6)
    # 2. Only generic words ("help", "fix", "please") without domain substance
    # 3. High multi-intent conflict (top category score close to runner up)
    generic_only = set(extracted_kws).issubset({"help", "hi", "hello", "question", "assistance", "contact"})
    
    if word_count < 6 or (generic_only and word_count < 10) or top_score == 0:
        assigned_category = CategoryEnum.GENERAL
        confidence = 0.52
        reason = "Ticket lacks sufficient domain-specific context or technical detail. Routed to human triage queue."
        urgency = UrgencyEnum.MEDIUM if "asap" in full_text or "urgent" in full_text else UrgencyEnum.LOW
        action = "Request clarification from customer regarding specific issue details and error messages."
        return assigned_category, urgency, round(confidence, 2), reason, action, extracted_kws

    if runner_up_score > 0 and (top_score - runner_up_score) <= 1.0 and top_score < 4.0:
        # Multi-intent conflict (e.g. billing + account)
        assigned_category = top_cat
        confidence = 0.62
        reason = f"Multi-intent detected between '{top_cat.value}' and '{runner_up_cat.value}'. Low score margin ({top_score:.1f} vs {runner_up_score:.1f})."
        urgency = UrgencyEnum.MEDIUM
        action = f"Human triage required to disambiguate primary intent between {top_cat.value} and {runner_up_cat.value}."
        return assigned_category, urgency, round(confidence, 2), reason, action, extracted_kws

    # Clear classification
    assigned_category = top_cat
    if runner_up_score > 0:
        margin_ratio = (top_score - runner_up_score) / (top_score + runner_up_score)
        confidence = min(0.96, max(0.76, 0.75 + (margin_ratio * 0.20)))
    else:
        confidence = min(0.96, max(0.82, 0.80 + (top_score * 0.03)))

    # Urgency analysis
    if any(ind in full_text for ind in CRITICAL_INDICATORS) or (assigned_category == CategoryEnum.SECURITY and confidence >= 0.80):
        urgency = UrgencyEnum.CRITICAL
    elif any(ind in full_text for ind in HIGH_INDICATORS) or assigned_category in [CategoryEnum.BILLING, CategoryEnum.ACCOUNT, CategoryEnum.TECHNICAL]:
        urgency = UrgencyEnum.HIGH
    elif any(ind in full_text for ind in LOW_INDICATORS) or assigned_category == CategoryEnum.PRODUCT:
        urgency = UrgencyEnum.LOW
    else:
        urgency = UrgencyEnum.MEDIUM

    # Synthesize explainable reason
    matched_kws_str = ", ".join([f"'{k}'" for k in extracted_kws[:4]])
    reason = f"Detected {assigned_category.value} domain indicators ({matched_kws_str}). Classification confidence: {confidence*100:.0f}%."

    # Recommended action synthesis
    actions = {
        CategoryEnum.BILLING: "Review customer payment ledger, verify duplicate charge/invoice, and issue refund/receipt.",
        CategoryEnum.TECHNICAL: "Inspect system telemetry/error logs, reproduce failure, and escalate to on-call engineering.",
        CategoryEnum.ACCOUNT: "Verify customer identity via secondary channel and provide secure password/MFA reset link.",
        CategoryEnum.SECURITY: "Immediately isolate suspicious sessions, revoke auth tokens, and initiate security audit.",
        CategoryEnum.ORDERS: "Check courier tracking API status, confirm shipping address, and initiate courier tracer.",
        CategoryEnum.PRODUCT: "Log feature request in product backlog and share current product roadmap with customer.",
        CategoryEnum.GENERAL: "Acknowledge inquiry and route to appropriate specialist or reply with informational FAQ."
    }
    recommended_action = actions.get(assigned_category, "Review ticket details and assign to tier 1 agent.")

    return assigned_category, urgency, round(confidence, 2), reason, recommended_action, extracted_kws
