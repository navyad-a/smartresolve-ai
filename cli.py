"""
Command Line Interface (CLI) for SmartResolve AI.
Allows single-ticket triage, batch CSV processing, and export directly from terminal.
"""

import sys
import csv
import argparse

# Ensure UTF-8 output encoding for Windows PowerShell/CMD
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.models import TicketInput
from src.agent import SupportTicketAgent


def print_table_fallback(table_data):
    """Simple terminal table renderer without external dependencies."""
    col_w1 = max(len(str(row[0])) for row in table_data) + 2
    col_w2 = max(len(str(row[1])) for row in table_data) + 2
    border = "+" + "-" * col_w1 + "+" + "-" * col_w2 + "+"
    print(border)
    for row in table_data:
        k = str(row[0]).ljust(col_w1 - 1)
        v = str(row[1]).ljust(col_w2 - 1)
        print(f"| {k}| {v}|")
    print(border)


def main():
    parser = argparse.ArgumentParser(
        description="SmartResolve AI - Autonomous Support Ticket Triage & Routing Agent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Single ticket command
    single_parser = subparsers.add_parser("triage", help="Triage a single ticket")
    single_parser.add_argument("--id", default="T001", help="Ticket ID")
    single_parser.add_argument("--subject", required=True, help="Ticket subject line")
    single_parser.add_argument("--body", required=True, help="Ticket body description")
    single_parser.add_argument("--tier", default="Standard", choices=["Standard", "Pro", "Enterprise"], help="Customer Tier")
    single_parser.add_argument("--threshold", type=float, default=0.75, help="Confidence threshold for human review")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch triage a CSV file of tickets")
    batch_parser.add_argument("--input", required=True, help="Path to input CSV file")
    batch_parser.add_argument("--output", default="data/sample_output.csv", help="Path to save output CSV file")
    batch_parser.add_argument("--threshold", type=float, default=0.75, help="Confidence threshold for human review")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    agent = SupportTicketAgent(confidence_threshold=args.threshold)

    if args.command == "triage":
        ticket = TicketInput(
            ticket_id=args.id,
            subject=args.subject,
            body=args.body,
            customer_tier=args.tier
        )
        print(f"\n[TRIAGE] Running SmartResolve AI Triage for [{ticket.ticket_id}]...")
        result = agent.triage(ticket)

        status_emoji = "[HUMAN REVIEW REQUIRED]" if result.human_review_required else "[AUTO-ROUTED]"
        table_data = [
            ["Ticket ID", result.ticket_id],
            ["Status", status_emoji],
            ["Category", result.category.value],
            ["Urgency", result.urgency.value],
            ["Confidence", f"{result.confidence * 100:.1f}%"],
            ["Assigned Queue/Team", result.assigned_team.value],
            ["Estimated SLA", f"{result.estimated_sla_hours} Hours"],
            ["Reasoning", result.reason],
            ["Recommended Action", result.recommended_action],
            ["Extracted Keywords", ", ".join(result.extracted_keywords) if result.extracted_keywords else "None"]
        ]

        try:
            from tabulate import tabulate
            print("\n" + tabulate(table_data, tablefmt="grid"))
        except ImportError:
            print("\n" + "=" * 50)
            print_table_fallback(table_data)

    elif args.command == "batch":
        print(f"\n[BATCH] Loading batch tickets from '{args.input}'...")
        tickets = []
        try:
            with open(args.input, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tickets.append(
                        TicketInput(
                            ticket_id=str(row["ticket_id"]),
                            subject=str(row["subject"]),
                            body=str(row["body"]),
                            customer_tier=str(row.get("customer_tier", "Standard"))
                        )
                    )
        except Exception as e:
            print(f"[ERROR] Error loading CSV: {e}")
            sys.exit(1)

        print(f"[PROCESS] Processing {len(tickets)} tickets...")
        results, summary = agent.triage_batch(tickets)

        # Write output CSV
        fieldnames = [
            "ticket_id", "category", "urgency", "confidence", "assigned_team",
            "human_review_required", "estimated_sla_hours", "reason",
            "recommended_action", "extracted_keywords"
        ]

        try:
            with open(args.output, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    writer.writerow({
                        "ticket_id": r.ticket_id,
                        "category": r.category.value,
                        "urgency": r.urgency.value,
                        "confidence": r.confidence,
                        "assigned_team": r.assigned_team.value,
                        "human_review_required": r.human_review_required,
                        "estimated_sla_hours": r.estimated_sla_hours,
                        "reason": r.reason,
                        "recommended_action": r.recommended_action,
                        "extracted_keywords": ", ".join(r.extracted_keywords)
                    })
            print(f"[SUCCESS] Batch triage complete! Results saved to '{args.output}'")
        except Exception as e:
            print(f"[ERROR] Error saving output CSV: {e}")
            sys.exit(1)

        print("\nBATCH EXECUTION SUMMARY:")
        summary_table = [
            ["Total Tickets Processed", str(summary.total_tickets)],
            ["Automatically Routed", f"{summary.auto_routed_count} ({summary.auto_routed_count/summary.total_tickets*100:.1f}%)"],
            ["Flagged for Human Review (<0.75)", f"{summary.human_review_count} ({summary.human_review_count/summary.total_tickets*100:.1f}%)"],
            ["Critical Urgency Incidents", str(summary.critical_urgency_count)],
            ["Average Model Confidence", f"{summary.average_confidence*100:.1f}%"]
        ]
        try:
            from tabulate import tabulate
            print(tabulate(summary_table, tablefmt="grid"))
        except ImportError:
            print_table_fallback(summary_table)


if __name__ == "__main__":
    main()
