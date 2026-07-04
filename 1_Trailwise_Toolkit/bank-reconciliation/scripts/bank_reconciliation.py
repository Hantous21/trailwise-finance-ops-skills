"""Bank reconciliation engine — match bank statement transactions to ledger entries.

Extracted from the bank-reconciliation SKILL.md.  Provides data classes, a
reconciler with three-pass fuzzy matching, and a report generator with
suggested journal entries.

Usage::

    from bank_reconciliation import BankReconciler, BankTransaction, LedgerEntry
    reconciler = BankReconciler()
    results = reconciler.reconcile(bank_txns, ledger_entries)
    report = reconciler.generate_report(results, bank_ending, book_ending)
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class MatchType(Enum):
    EXACT = "exact"                # Same amount, same date, matching description
    HIGH_CONFIDENCE = "high"      # Same amount, date within 3 days, similar description
    LOW_CONFIDENCE = "low"        # Same amount, date within 7 days, different description
    UNMATCHED = "unmatched"
    DUPLICATE = "duplicate"        # Multiple ledger entries match one bank transaction


class TransactionSide(Enum):
    BANK_ONLY = "bank_only"       # In bank statement, not in ledger
    LEDGER_ONLY = "ledger_only"   # In ledger, not in bank statement
    MATCHED = "matched"


@dataclass
class BankTransaction:
    id: str
    date: date
    amount: float                   # Positive = deposit, negative = withdrawal
    description: str
    running_balance: Optional[float] = None


@dataclass
class LedgerEntry:
    id: str
    date: date
    amount: float                   # Positive = debit (increase), negative = credit (decrease)
    description: str
    account: str
    reference: str = ""


@dataclass
class MatchResult:
    bank_transaction: Optional[BankTransaction]
    ledger_entry: Optional[LedgerEntry]
    match_type: MatchType
    match_confidence: float         # 0-1
    match_reason: str
    side: TransactionSide


class BankReconciler:
    """Match bank transactions to ledger entries with fuzzy matching."""

    def __init__(self, date_tolerance_days: int = 3, amount_tolerance: float = 0.01,
                 description_similarity_threshold: float = 0.6):
        self.date_tolerance = date_tolerance_days
        self.amount_tolerance = amount_tolerance
        self.desc_threshold = description_similarity_threshold

    def reconcile(self, bank_txns: List[BankTransaction],
                  ledger_entries: List[LedgerEntry]) -> List[MatchResult]:
        """Reconcile bank statement against ledger entries."""
        results = []
        matched_bank_ids = set()
        matched_ledger_ids = set()

        # Pass 1: Exact matches (amount + date + description)
        for bt in bank_txns:
            for le in ledger_entries:
                if le.id in matched_ledger_ids:
                    continue
                if (abs(bt.amount - le.amount) <= self.amount_tolerance and
                    bt.date == le.date and
                    self._description_similarity(bt.description, le.description) > 0.8):
                    results.append(MatchResult(
                        bank_transaction=bt, ledger_entry=le,
                        match_type=MatchType.EXACT, match_confidence=1.0,
                        match_reason=f"Exact: ${bt.amount} on {bt.date}",
                        side=TransactionSide.MATCHED
                    ))
                    matched_bank_ids.add(bt.id)
                    matched_ledger_ids.add(le.id)
                    break

        # Pass 2: High confidence (amount + date within tolerance)
        for bt in bank_txns:
            if bt.id in matched_bank_ids:
                continue
            best_match = None
            best_score = 0
            for le in ledger_entries:
                if le.id in matched_ledger_ids:
                    continue
                if abs(bt.amount - le.amount) <= self.amount_tolerance:
                    date_diff = abs((bt.date - le.date).days)
                    if date_diff <= self.date_tolerance:
                        desc_sim = self._description_similarity(bt.description, le.description)
                        score = 0.5 + (desc_sim * 0.5)  # 0.5-1.0 range
                        if score > best_score:
                            best_score = score
                            best_match = le

            if best_match:
                results.append(MatchResult(
                    bank_transaction=bt, ledger_entry=best_match,
                    match_type=MatchType.HIGH_CONFIDENCE,
                    match_confidence=best_score,
                    match_reason=f"Amount match, date within {abs((bt.date - best_match.date).days)} days",
                    side=TransactionSide.MATCHED
                ))
                matched_bank_ids.add(bt.id)
                matched_ledger_ids.add(best_match.id)

        # Pass 3: Low confidence (amount only, wider date range)
        for bt in bank_txns:
            if bt.id in matched_bank_ids:
                continue
            for le in ledger_entries:
                if le.id in matched_ledger_ids:
                    continue
                if abs(bt.amount - le.amount) <= self.amount_tolerance:
                    date_diff = abs((bt.date - le.date).days)
                    if date_diff <= 7:
                        results.append(MatchResult(
                            bank_transaction=bt, ledger_entry=le,
                            match_type=MatchType.LOW_CONFIDENCE,
                            match_confidence=0.4,
                            match_reason=f"Amount match, date {date_diff} days apart, desc mismatch",
                            side=TransactionSide.MATCHED
                        ))
                        matched_bank_ids.add(bt.id)
                        matched_ledger_ids.add(le.id)
                        break

        # Unmatched bank transactions
        for bt in bank_txns:
            if bt.id not in matched_bank_ids:
                results.append(MatchResult(
                    bank_transaction=bt, ledger_entry=None,
                    match_type=MatchType.UNMATCHED,
                    match_confidence=0,
                    match_reason="No matching ledger entry found",
                    side=TransactionSide.BANK_ONLY
                ))

        # Unmatched ledger entries
        for le in ledger_entries:
            if le.id not in matched_ledger_ids:
                results.append(MatchResult(
                    bank_transaction=None, ledger_entry=le,
                    match_type=MatchType.UNMATCHED,
                    match_confidence=0,
                    match_reason="No matching bank transaction",
                    side=TransactionSide.LEDGER_ONLY
                ))

        return results

    def generate_report(self, results: List[MatchResult],
                        bank_ending_balance: float,
                        book_ending_balance: float) -> Dict:
        """Generate reconciliation summary report."""
        matched = [r for r in results if r.side == TransactionSide.MATCHED]
        bank_only = [r for r in results if r.side == TransactionSide.BANK_ONLY]
        ledger_only = [r for r in results if r.side == TransactionSide.LEDGER_ONLY]

        # Deposits in transit (positive ledger-only entries)
        deposits_in_transit = [r for r in ledger_only if r.ledger_entry.amount > 0]
        # Outstanding checks (negative ledger-only entries)
        outstanding_checks = [r for r in ledger_only if r.ledger_entry.amount < 0]
        # Bank fees/interest (bank-only)
        bank_fees = [r for r in bank_only if r.bank_transaction.amount < 0]
        bank_interest = [r for r in bank_only if r.bank_transaction.amount > 0]

        # Adjusted balances
        adj_bank = bank_ending_balance + sum(r.ledger_entry.amount for r in deposits_in_transit) - sum(abs(r.ledger_entry.amount) for r in outstanding_checks)
        adj_book = book_ending_balance - sum(abs(r.bank_transaction.amount) for r in bank_fees) + sum(r.bank_transaction.amount for r in bank_interest)

        return {
            "bank_ending_balance": round(bank_ending_balance, 2),
            "book_ending_balance": round(book_ending_balance, 2),
            "matched_count": len(matched),
            "unmatched_bank": len(bank_only),
            "unmatched_ledger": len(ledger_only),
            "deposits_in_transit": len(deposits_in_transit),
            "outstanding_checks": len(outstanding_checks),
            "bank_fees": len(bank_fees),
            "bank_interest": len(bank_interest),
            "adjusted_bank_balance": round(adj_bank, 2),
            "adjusted_book_balance": round(adj_book, 2),
            "is_reconciled": abs(adj_bank - adj_book) < 0.01,
            "difference": round(adj_bank - adj_book, 2),
            "suggested_journal_entries": self._suggest_entries(bank_fees, bank_interest),
        }

    def _suggest_entries(self, bank_fees: List[MatchResult],
                        bank_interest: List[MatchResult]) -> List[Dict]:
        """Suggest journal entries for bank-only transactions."""
        entries = []
        for r in bank_fees:
            entries.append({
                "entry": "Bank Fee Expense",
                "debit": abs(r.bank_transaction.amount),
                "credit": 0,
                "description": f"Bank fee: {r.bank_transaction.description}",
                "date": r.bank_transaction.date.isoformat(),
            })
            entries.append({
                "entry": "Cash - Operating",
                "debit": 0,
                "credit": abs(r.bank_transaction.amount),
                "description": f"Bank fee: {r.bank_transaction.description}",
                "date": r.bank_transaction.date.isoformat(),
            })

        for r in bank_interest:
            entries.append({
                "entry": "Cash - Operating",
                "debit": r.bank_transaction.amount,
                "credit": 0,
                "description": f"Interest income: {r.bank_transaction.description}",
                "date": r.bank_transaction.date.isoformat(),
            })
            entries.append({
                "entry": "Interest Income",
                "debit": 0,
                "credit": r.bank_transaction.amount,
                "description": f"Interest income: {r.bank_transaction.description}",
                "date": r.bank_transaction.date.isoformat(),
            })

        return entries

    def _description_similarity(self, s1: str, s2: str) -> float:
        """Simple word-overlap similarity score (0-1)."""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        if not words1 or not words2:
            return 0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)
