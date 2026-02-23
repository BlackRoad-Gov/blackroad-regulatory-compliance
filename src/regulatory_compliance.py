#!/usr/bin/env python3
"""BlackRoad Regulatory Compliance Tracker - Production Module.

Tracks regulatory requirements, compliance audits, and violations
with persistent SQLite storage and colorized CLI output.
"""

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

RED     = "\033[0;31m"
GREEN   = "\033[0;32m"
YELLOW  = "\033[1;33m"
CYAN    = "\033[0;36m"
BLUE    = "\033[0;34m"
MAGENTA = "\033[0;35m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
NC      = "\033[0m"

DB_PATH = Path.home() / ".blackroad" / "regulatory_compliance.db"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Regulation:
    code: str
    name: str
    jurisdiction: str
    category: str
    effective_date: str
    status: str = "active"
    created_at: str = ""
    id: Optional[int] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class ComplianceAudit:
    regulation_code: str
    entity: str
    result: str          # compliant | non_compliant | partial | pending
    audit_date: str
    auditor: str = "system"
    notes: str = ""
    evidence_url: str = ""
    created_at: str = ""
    id: Optional[int] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.audit_date:
            self.audit_date = datetime.now().date().isoformat()


@dataclass
class Violation:
    regulation_code: str
    entity: str
    severity: str        # low | medium | high | critical
    description: str
    reported_at: str = ""
    resolved: bool = False
    remediation: str = ""
    penalty_amount: float = 0.0
    id: Optional[int] = None

    def __post_init__(self):
        if not self.reported_at:
            self.reported_at = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Database / Business Logic
# ---------------------------------------------------------------------------

class RegulatoryComplianceTracker:
    """Production regulatory compliance tracker with SQLite persistence."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS regulations (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    code          TEXT UNIQUE NOT NULL,
                    name          TEXT NOT NULL,
                    jurisdiction  TEXT NOT NULL,
                    category      TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    status        TEXT DEFAULT 'active',
                    created_at    TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS compliance_audits (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    regulation_code TEXT NOT NULL,
                    entity          TEXT NOT NULL,
                    result          TEXT NOT NULL,
                    audit_date      TEXT NOT NULL,
                    auditor         TEXT DEFAULT 'system',
                    notes           TEXT DEFAULT '',
                    evidence_url    TEXT DEFAULT '',
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (regulation_code) REFERENCES regulations(code)
                );
                CREATE TABLE IF NOT EXISTS violations (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    regulation_code TEXT NOT NULL,
                    entity          TEXT NOT NULL,
                    severity        TEXT NOT NULL,
                    description     TEXT NOT NULL,
                    reported_at     TEXT NOT NULL,
                    resolved        INTEGER DEFAULT 0,
                    remediation     TEXT DEFAULT '',
                    penalty_amount  REAL DEFAULT 0.0,
                    FOREIGN KEY (regulation_code) REFERENCES regulations(code)
                );
                CREATE INDEX IF NOT EXISTS idx_audits_code ON compliance_audits(regulation_code);
                CREATE INDEX IF NOT EXISTS idx_violations_code ON violations(regulation_code);
            """)

    def add_regulation(self, code: str, name: str, jurisdiction: str,
                       category: str, effective_date: str) -> Regulation:
        """Register a new regulatory requirement."""
        reg = Regulation(code=code, name=name, jurisdiction=jurisdiction,
                         category=category, effective_date=effective_date)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO regulations (code, name, jurisdiction, category, "
                "effective_date, status, created_at) VALUES (?,?,?,?,?,?,?)",
                (reg.code, reg.name, reg.jurisdiction, reg.category,
                 reg.effective_date, reg.status, reg.created_at)
            )
            reg.id = cur.lastrowid
        return reg

    def list_regulations(self, status: Optional[str] = None,
                         jurisdiction: Optional[str] = None) -> List[dict]:
        """List regulations with optional filtering."""
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if jurisdiction:
            clauses.append("jurisdiction = ?")
            params.append(jurisdiction)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM regulations {where} ORDER BY created_at DESC",
                params
            ).fetchall()
        return [dict(r) for r in rows]

    def record_audit(self, regulation_code: str, entity: str, result: str,
                     auditor: str = "system", notes: str = "") -> ComplianceAudit:
        """Record a compliance audit result."""
        audit = ComplianceAudit(
            regulation_code=regulation_code, entity=entity, result=result,
            audit_date=datetime.now().date().isoformat(),
            auditor=auditor, notes=notes
        )
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO compliance_audits (regulation_code, entity, result, "
                "audit_date, auditor, notes, evidence_url, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (audit.regulation_code, audit.entity, audit.result,
                 audit.audit_date, audit.auditor, audit.notes,
                 audit.evidence_url, audit.created_at)
            )
            audit.id = cur.lastrowid
        return audit

    def report_violation(self, regulation_code: str, entity: str,
                         severity: str, description: str,
                         penalty: float = 0.0) -> Violation:
        """Report a compliance violation with optional penalty amount."""
        v = Violation(regulation_code=regulation_code, entity=entity,
                      severity=severity, description=description,
                      penalty_amount=penalty)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO violations (regulation_code, entity, severity, "
                "description, reported_at, resolved, remediation, penalty_amount) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (v.regulation_code, v.entity, v.severity, v.description,
                 v.reported_at, int(v.resolved), v.remediation, v.penalty_amount)
            )
            v.id = cur.lastrowid
        return v

    def get_summary(self) -> dict:
        """Aggregate compliance statistics across all regulations."""
        with self._conn() as conn:
            regs   = conn.execute("SELECT COUNT(*) FROM regulations").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM regulations WHERE status='active'"
            ).fetchone()[0]
            audits = conn.execute("SELECT COUNT(*) FROM compliance_audits").fetchone()[0]
            ok     = conn.execute(
                "SELECT COUNT(*) FROM compliance_audits WHERE result='compliant'"
            ).fetchone()[0]
            open_v = conn.execute(
                "SELECT COUNT(*) FROM violations WHERE resolved=0"
            ).fetchone()[0]
            crit   = conn.execute(
                "SELECT COUNT(*) FROM violations WHERE severity='critical' AND resolved=0"
            ).fetchone()[0]
            fines  = conn.execute(
                "SELECT COALESCE(SUM(penalty_amount),0) FROM violations"
            ).fetchone()[0]
        return {
            "total_regulations":   regs,
            "active_regulations":  active,
            "total_audits":        audits,
            "compliant_audits":    ok,
            "compliance_rate":     f"{ok / audits * 100:.1f}%" if audits else "N/A",
            "open_violations":     open_v,
            "critical_violations": crit,
            "total_penalties_usd": f"${fines:,.2f}",
        }

    def export_report(self, output_path: str = "compliance_report.json") -> str:
        """Export full compliance report to JSON."""
        with self._conn() as conn:
            violations = [dict(r) for r in conn.execute(
                "SELECT * FROM violations ORDER BY reported_at DESC"
            ).fetchall()]
            audits = [dict(r) for r in conn.execute(
                "SELECT * FROM compliance_audits ORDER BY created_at DESC LIMIT 200"
            ).fetchall()]
        data = {
            "exported_at": datetime.now().isoformat(),
            "generator":   "BlackRoad Regulatory Compliance Tracker v1.0",
            "summary":     self.get_summary(),
            "regulations": self.list_regulations(),
            "recent_audits": audits,
            "violations":  violations,
        }
        Path(output_path).write_text(json.dumps(data, indent=2))
        return output_path


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _header(title: str):
    w = 64
    print(f"\n{BOLD}{BLUE}{'━' * w}{NC}")
    print(f"{BOLD}{BLUE}  {title}{NC}")
    print(f"{BOLD}{BLUE}{'━' * w}{NC}")


def _severity_badge(severity: str) -> str:
    c = {"critical": RED + BOLD, "high": RED, "medium": YELLOW, "low": CYAN}.get(
        severity.lower(), NC)
    return f"{c}[{severity.upper()}]{NC}"


def _result_badge(result: str) -> str:
    c = {"compliant": GREEN, "non_compliant": RED,
         "partial": YELLOW, "pending": MAGENTA}.get(result.lower(), NC)
    return f"{c}{result}{NC}"


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_list(args, tracker: RegulatoryComplianceTracker):
    regs = tracker.list_regulations(
        status=getattr(args, "status", None),
        jurisdiction=getattr(args, "jurisdiction", None),
    )
    _header("REGULATORY COMPLIANCE TRACKER — Regulations")
    if not regs:
        print(f"  {YELLOW}No regulations found.{NC}\n")
        return
    for r in regs:
        sc = GREEN if r["status"] == "active" else DIM
        print(f"  {CYAN}#{r['id']:03d}{NC}  {BOLD}{r['code']:<20}{NC} {r['name']}")
        print(f"       {DIM}Jurisdiction:{NC} {r['jurisdiction']:<12} "
              f"{DIM}Category:{NC} {r['category']:<15} "
              f"{DIM}Effective:{NC} {r['effective_date']}")
        print(f"       Status: {sc}{r['status']}{NC}")
        print()


def cmd_add(args, tracker: RegulatoryComplianceTracker):
    reg = tracker.add_regulation(
        args.code, args.name, args.jurisdiction, args.category, args.date
    )
    print(f"\n{GREEN}✓ Regulation registered{NC}")
    print(f"  {BOLD}ID:{NC}           {reg.id}")
    print(f"  {BOLD}Code:{NC}         {reg.code}")
    print(f"  {BOLD}Name:{NC}         {reg.name}")
    print(f"  {BOLD}Jurisdiction:{NC} {reg.jurisdiction}")
    print(f"  {BOLD}Effective:{NC}    {reg.effective_date}\n")


def cmd_status(args, tracker: RegulatoryComplianceTracker):
    s = tracker.get_summary()
    _header("COMPLIANCE STATUS SUMMARY")
    pairs = [
        ("Total Regulations",   s["total_regulations"],   CYAN),
        ("Active Regulations",  s["active_regulations"],  GREEN),
        ("Total Audits",        s["total_audits"],        CYAN),
        ("Compliant Audits",    s["compliant_audits"],    GREEN),
        ("Compliance Rate",     s["compliance_rate"],     BOLD + GREEN),
        ("Open Violations",     s["open_violations"],     YELLOW if s["open_violations"] else GREEN),
        ("Critical Violations", s["critical_violations"], RED if s["critical_violations"] else GREEN),
        ("Total Penalties",     s["total_penalties_usd"], RED if s["total_penalties_usd"] != "$0.00" else GREEN),
    ]
    for label, val, color in pairs:
        print(f"  {DIM}{label:<25}{NC}  {color}{val}{NC}")
    print()


def cmd_export(args, tracker: RegulatoryComplianceTracker):
    path = tracker.export_report(args.output)
    print(f"\n{GREEN}✓ Compliance report exported{NC}")
    print(f"  {BOLD}Path:{NC} {path}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    tracker = RegulatoryComplianceTracker()
    parser = argparse.ArgumentParser(
        prog="regulatory-compliance",
        description=f"{BOLD}BlackRoad Regulatory Compliance Tracker{NC}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s add --code GDPR-001 --name 'Data Protection' "
            "--jurisdiction EU --category Privacy --date 2018-05-25\n"
            "  %(prog)s list --status active\n"
            "  %(prog)s status\n"
            "  %(prog)s export --output report.json\n"
        ),
    )
    subs = parser.add_subparsers(dest="command", metavar="COMMAND")
    subs.required = True

    p = subs.add_parser("list", help="List all regulations")
    p.add_argument("--status", choices=["active", "inactive"])
    p.add_argument("--jurisdiction", help="Filter by jurisdiction code")

    p = subs.add_parser("add", help="Add a new regulation")
    p.add_argument("--code",         required=True, metavar="CODE")
    p.add_argument("--name",         required=True, metavar="NAME")
    p.add_argument("--jurisdiction", required=True, metavar="EU|US|UK")
    p.add_argument("--category",     required=True, metavar="Privacy|Finance|...")
    p.add_argument("--date",         required=True, metavar="YYYY-MM-DD")

    subs.add_parser("status", help="Show compliance status summary")

    p = subs.add_parser("export", help="Export full compliance report")
    p.add_argument("--output", default="compliance_report.json", metavar="FILE")

    args = parser.parse_args()
    {"list": cmd_list, "add": cmd_add,
     "status": cmd_status, "export": cmd_export}[args.command](args, tracker)


if __name__ == "__main__":
    main()
