"""Populate the DEMO database (geolegalvault_demo) with a realistic spread of documents, through the real API.

Run (backend venv; the backend must already be running on :8001 against geolegalvault_demo, worker NOT running):
    backend/.venv/Scripts/python.exe demo/seed_realistic.py            # seed, then verify + report
    backend/.venv/Scripts/python.exe demo/seed_realistic.py --report   # report only, change nothing

What it does: logs in as each demo role (password read from scripts/seed.py, never printed), uploads short generated
PDFs from inside the "HQ Campus (demo)" fence, and drives submit / review / approve / archive over HTTP. Nothing is
inserted into MongoDB directly. Idempotent: a document whose title already exists is not re-uploaded; one that is
behind its target state is advanced.

Safety: refuses unless the running backend demonstrably writes to geolegalvault_demo (probe: one login must add an
audit row to the demo DB and none to the dev DB "geolegalvault"). Real Sepolia anchoring happens only for the
documents whose target is ACTIVE/ARCHIVED, after a wallet-balance gate (>= 10x the estimated cost).
PDF rendering needs reportlab; if the current interpreter lacks it, it is rendered by demo_video/.venv.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DB, DEV_DB = "geolegalvault_demo", "geolegalvault"

# Everything this process touches must be the demo DB, whatever .env says.
if os.environ.get("MONGODB_DB", DEMO_DB) != DEMO_DB:
    sys.exit(f"REFUSED: MONGODB_DB is set to a database other than {DEMO_DB!r} in this environment.")
os.environ["MONGODB_DB"] = DEMO_DB

API = "http://localhost:8001/api/v1"
INSIDE = {"lat": 11.67, "lng": 78.15, "accuracy": 20}
OUTSIDE = {"lat": 11.00, "lng": 77.00, "accuracy": 20}
EMAILS = {
    "staff": "authorized_staff@geolegalvault.demo",
    "reviewer": "reviewing_officer@geolegalvault.demo",
    "legal": "legal_officer@geolegalvault.demo",
    "admin": "administrator@geolegalvault.demo",
    "auditor": "auditor@geolegalvault.demo",
}
PDF_DIR = ROOT / "demo" / "seed_pdfs"
# Staff may upload up to CONFIDENTIAL, the Legal Officer up to RESTRICTED (PROPOSED_ROLE_CLEARANCE).
# Legal-officer uploads cannot be approved: approver must differ from uploader and there is one Legal Officer.
# target: DRAFT | SUBMITTED | PENDING_APPROVAL | CHANGES (reviewer requests changes -> DRAFT + feedback)
#         | ACTIVE | ARCHIVED
# (title, doc_type, classification, uploader, target, parties/amount for body text, reviewer comment)
S, L = "staff", "legal"
DOCS = [
    ("Commercial Lease - Anna Salai Warehouse Unit 4", "LEASE", "CONFIDENTIAL", S, "ACTIVE", ("Meridian Logistics Pvt Ltd", "Kavin Estates LLP", "INR 1,85,000 per month"), None),
    ("Vendor Services Agreement - Northwind Facilities 2026", "VENDOR_AGREEMENT", "INTERNAL", S, "ACTIVE", ("GeoLegalVault Records Office", "Northwind Facilities Ltd", "INR 6,40,000 per year"), None),
    ("Board Resolution 2026-07 - Approval of FY27 Budget", "BOARD_RESOLUTION", "PUBLIC", S, "ACTIVE", ("The Board of Directors", "Company Secretary", "INR 12.5 crore"), None),
    ("Mutual NDA - Harlow Analytics Partnership", "NDA", "INTERNAL", S, "ARCHIVED", ("GeoLegalVault Records Office", "Harlow Analytics Inc", "no monetary value"), None),
    ("Settlement Letter - Rao v. Sundaram Traders", "SETTLEMENT", "CONFIDENTIAL", S, "PENDING_APPROVAL", ("Mr. R. Rao", "Sundaram Traders", "INR 4,25,000"), None),
    ("Vendor Agreement - Brightline Office Supplies", "VENDOR_AGREEMENT", "INTERNAL", S, "PENDING_APPROVAL", ("GeoLegalVault Records Office", "Brightline Supplies Pvt Ltd", "INR 2,10,000 per year"), None),
    ("Employment Contract - Senior Records Analyst (S. Iyer)", "EMPLOYMENT", "CONFIDENTIAL", S, "SUBMITTED", ("GeoLegalVault Records Office", "Ms. S. Iyer", "INR 14,40,000 per year"), None),
    ("Compliance Notice - Data Retention Schedule Update", "COMPLIANCE_NOTICE", "INTERNAL", S, "SUBMITTED", ("Compliance Office", "All Departments", "not applicable"), None),
    ("Sublease Agreement - Third Floor Annexe", "LEASE", "CONFIDENTIAL", S, "SUBMITTED", ("GeoLegalVault Records Office", "Orchid Co-working LLP", "INR 95,000 per month"), None),
    ("Service Level Agreement - Cloud Hosting Provider", "VENDOR_AGREEMENT", "INTERNAL", S, "SUBMITTED", ("GeoLegalVault Records Office", "Stratus Hosting Ltd", "INR 3,60,000 per year"), None),
    ("Power of Attorney - Branch Registration Filing", "POWER_OF_ATTORNEY", "CONFIDENTIAL", S, "DRAFT", ("Managing Director", "Adv. T. Krishnan", "not applicable"), None),
    ("Public Notice - Change of Registered Office", "NOTICE", "PUBLIC", S, "DRAFT", ("GeoLegalVault Records Office", "General Public", "not applicable"), None),
    ("Internal Memo - Document Handling Procedure v3", "MEMO", "INTERNAL", S, "DRAFT", ("Records Office", "All Staff", "not applicable"), None),
    ("Licence Agreement - Mapping Data Subscription", "LICENCE", "INTERNAL", S, "CHANGES", ("GeoLegalVault Records Office", "TerraMaps Data Ltd", "INR 5,20,000 per year"),
     "Clause 7 (term and renewal) is missing the notice period. Please add a 60-day notice and resubmit."),
    ("Consultancy Agreement - Audit Readiness Review", "CONSULTANCY", "CONFIDENTIAL", S, "CHANGES", ("GeoLegalVault Records Office", "Veritas Advisory LLP", "INR 8,75,000 fixed fee"),
     "Fee schedule does not match the statement of work (milestone 3). Please reconcile before resubmission."),
    ("Termination Letter - Legacy Storage Contract", "TERMINATION", "CONFIDENTIAL", L, "DRAFT", ("GeoLegalVault Records Office", "OldVault Storage Ltd", "INR 1,20,000 settlement"), None),
    ("Regulatory Compliance Notice - Cross-Border Data Transfer", "COMPLIANCE_NOTICE", "RESTRICTED", L, "SUBMITTED", ("Legal Department", "Data Protection Authority", "not applicable"), None),
    ("Litigation Hold Notice - Vendor Dispute 2026-03", "LEGAL_HOLD", "RESTRICTED", L, "PENDING_APPROVAL", ("Legal Department", "All Custodians", "not applicable"), None),
    ("Shareholder Agreement Amendment - Series B Terms", "SHAREHOLDER", "CONFIDENTIAL", L, "PENDING_APPROVAL", ("Existing Shareholders", "Meridian Ventures Fund", "INR 40 crore"), None),
    ("Whistleblower Case Summary - Internal Review 0412", "CASE_SUMMARY", "RESTRICTED", L, "CHANGES", ("Legal Department", "Audit Committee", "not applicable"),
     "Summary names the complainant in section 2. Redact identifying detail and resubmit."),
]
STAGE = {"DRAFT": 0, "SUBMITTED": 1, "PENDING_APPROVAL": 2, "ACTIVE": 3, "ARCHIVED": 4}
PASSWORD = re.search(r'DEMO_PASSWORD\s*=\s*"([^"]+)"', (ROOT / "scripts" / "seed.py").read_text("utf-8")).group(1)


# ---------------------------------------------------------------------------------------------------- PDFs
def _body(i: int, title: str, doc_type: str, classification: str, parties: tuple, ) -> list[str]:
    a, b, amount = parties
    ref = f"GLV-DEMO-{i + 1:03d}"
    return [
        f"Reference {ref} | Classification: {classification} | Type: {doc_type.replace('_', ' ').title()}",
        f"This document is made between {a} (the First Party) and {b} (the Second Party). "
        "All names are fictional and used for demonstration only.",
        f"1. Subject. The parties record their understanding in relation to: {title}.",
        f"2. Consideration. The agreed consideration is {amount}, payable as set out in the schedule to {ref}.",
        f"3. Term. This document takes effect on its approval date and remains in force for {12 + (i % 4) * 6} months "
        "unless ended earlier in writing.",
        f"4. Confidentiality. Each party keeps the contents of {ref} confidential, consistent with the classification above.",
        "5. Governing law. Indian law, with disputes referred to the courts of Chennai.",
        "Signed for and on behalf of the parties (demo placeholder, no real signatories).",
    ]


def render_pdfs(items: list[dict]) -> None:
    """items: [{path, title, paras}]. Needs reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    for it in items:
        story = [Paragraph(it["title"], styles["Title"]), Spacer(1, 12)]
        for para in it["paras"]:
            story += [Paragraph(para, styles["BodyText"]), Spacer(1, 8)]
        SimpleDocTemplate(it["path"], pagesize=A4, title=it["title"], author="GeoLegalVault demo",
                          invariant=1).build(story)  # invariant: same text -> same bytes on a rerun


if __name__ == "__main__" and "--render" in sys.argv:  # child mode, run by a reportlab-capable interpreter
    render_pdfs(json.loads(sys.stdin.read()))
    sys.exit(0)


def make_pdfs() -> dict[str, Path]:
    PDF_DIR.mkdir(exist_ok=True)
    items, out = [], {}
    for i, (title, doc_type, cls, _who, _t, parties, _c) in enumerate(DOCS):
        path = PDF_DIR / f"seed_{i + 1:02d}.pdf"
        out[title] = path
        items.append({"path": str(path), "title": title, "paras": _body(i, title, doc_type, cls, parties)})
    try:
        import reportlab  # noqa: F401
        render_pdfs(items)
    except ImportError:
        venv_py = ROOT / "demo_video" / ".venv" / "Scripts" / "python.exe"
        subprocess.run([str(venv_py), str(Path(__file__)), "--render"], input=json.dumps(items), text=True, check=True)
    return out


# ---------------------------------------------------------------------------------------------------- HTTP
import httpx  # noqa: E402  (after the --render child path, which has no httpx)

_client = httpx.Client(base_url=API, timeout=120)
_tokens: dict[str, str] = {}


def login(role: str) -> str:
    if role not in _tokens:
        r = _client.post("/auth/login", json={"email": EMAILS[role], "password": PASSWORD})
        r.raise_for_status()
        _tokens[role] = r.json()["access_token"]
    return _tokens[role]


def req(role: str, method: str, path: str, *, loc: dict | None = None, **kw) -> httpx.Response:
    headers = {"Authorization": f"Bearer {login(role)}"}
    if loc is not None:
        headers.update({"X-Geo-Lat": str(loc["lat"]), "X-Geo-Lng": str(loc["lng"]),
                        "X-Geo-Accuracy": str(loc["accuracy"]), "X-Geo-Timestamp": str(time.time())})
    return _client.request(method, path, headers=headers, **kw)


def all_documents(role: str = "legal", include_archived: bool = False) -> list[dict]:
    """The default list hides ARCHIVED documents (by design); include_archived adds them with status=ARCHIVED."""
    out = []
    for status in ([None, "ARCHIVED"] if include_archived else [None]):
        page = 1
        while True:
            params = {"limit": 100, "page": page, **({"status": status} if status else {})}
            d = req(role, "GET", "/documents", params=params).json()
            out += d["items"]
            if page * 100 >= d["total"]:
                break
            page += 1
    return out


# ---------------------------------------------------------------------------------------------------- safety
def assert_backend_is_demo() -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.core.config import get_settings

    async def counts(c):
        return {n: await c[n].audit_logs.count_documents({}) for n in (DEMO_DB, DEV_DB)}

    async def probe():
        c = AsyncIOMotorClient(get_settings().MONGODB_URI)  # URI used only to connect, never printed
        before = await counts(c)
        r = _client.post("/auth/login", json={"email": EMAILS["admin"], "password": PASSWORD})
        r.raise_for_status()
        after = await counts(c)
        return before, after

    before, after = asyncio.run(probe())
    if not (after[DEMO_DB] == before[DEMO_DB] + 1 and after[DEV_DB] == before[DEV_DB]):
        sys.exit(f"REFUSED: the backend on :8001 does not look like it writes to {DEMO_DB!r} "
                 f"(audit rows before {before}, after {after}).")
    print(f"[safety] backend on :8001 writes to {DEMO_DB} (login probe: demo audit +1, dev audit +0). OK")


# ---------------------------------------------------------------------------------------------------- wallet
def wallet(estimate: bool = False):
    sys.path.insert(0, str(ROOT / "backend"))
    from web3 import Web3
    from app.services.blockchain import get_contract, get_service_account, get_web3

    w3, acct = get_web3(), get_service_account()
    bal = w3.eth.get_balance(acct.address)
    if not estimate:
        return acct.address, bal
    import secrets
    gas = get_contract().functions.anchor("estimate-" + secrets.token_hex(8), 1, secrets.token_bytes(32), 1) \
        .estimate_gas({"from": acct.address})
    return acct.address, bal, int(gas * 1.2) * w3.eth.gas_price, Web3


def eth(wei: int) -> str:
    return f"{wei / 10**18:.18f} ETH"


# ---------------------------------------------------------------------------------------------------- seeding
def advance(i: int, doc: dict, row: tuple, anchors: list) -> str:
    """Drive one document to its target from its current status. Returns the final status."""
    title, _t, _c, who, target, _p, comment = row
    did = doc["id"]
    status = doc["status"]

    def step(role, action, **kw):
        r = req(role, "POST", f"/documents/{did}/{action}", **kw)
        if r.status_code >= 400:
            sys.exit(f"STOP: {action} on {title!r} as {role} returned {r.status_code}: {r.text[:300]}")
        return r.json()

    if target == "DRAFT":
        return status
    if status == "DRAFT" and doc.get("review_feedback") is None:
        status = step(who, "submit")["status"]
        print(f"  submit      -> {status}")
    if target == "SUBMITTED":
        return status
    if target == "CHANGES":
        if status == "SUBMITTED":
            status = step("reviewer", "review", json={"decision": "changes_requested", "comment": comment})["status"]
            print(f"  review      -> changes requested -> {status}")
        return status
    if status == "SUBMITTED":
        status = step("reviewer", "review", json={"decision": "approve", "comment": "Reviewed; terms are in order."})["status"]
        print(f"  review      -> {status}")
    if target == "PENDING_APPROVAL":
        return status
    if status == "PENDING_APPROVAL":
        res = step("legal", "approve", loc=INSIDE)
        status = res["status"]
        anchors.append((title, res.get("anchor_status"), res.get("tx_hash")))
        print(f"  approve     -> {status}  anchor={res.get('anchor_status')}  tx={res.get('tx_hash')}")
        if status != "ACTIVE":
            sys.exit(f"STOP: {title!r} did not reach ACTIVE after approval (status {status}). Not approving further "
                     "documents; with no worker running this would leave a stuck anchor.")
    if target == "ARCHIVED" and status == "ACTIVE":
        status = step("legal", "archive")["status"]
        print(f"  archive     -> {status}")
    return status


def seed() -> None:
    pdfs = make_pdfs()
    existing = {d["title"]: d for d in all_documents(include_archived=True)}
    fresh_db = not existing
    chain_work = [r for r in DOCS if r[4] in ("ACTIVE", "ARCHIVED")
                  and (r[0] not in existing or existing[r[0]]["status"] not in ("ACTIVE", "ARCHIVED"))]
    addr = bal_before = None
    if chain_work:
        addr, bal, per_tx, _ = wallet(estimate=True)
        need = per_tx * len(chain_work)
        print(f"[wallet] {addr}  balance {eth(bal)}")
        print(f"[wallet] {len(chain_work)} anchor transaction(s) planned; worst-case cost {eth(need)} "
              f"({eth(per_tx)} each); balance is {bal / need:,.0f}x that")
        if bal < 10 * need:
            sys.exit("STOP: wallet balance is below 10x the estimated cost. Not sending anything.")
        bal_before = bal

    anchors: list = []
    for i, row in enumerate(DOCS):
        title, doc_type, cls, who, target, _p, _c = row
        print(f"[{i + 1:02d}/{len(DOCS)}] {title}  ({cls}, {who}, target {target})")
        doc = existing.get(title)
        if doc is None:
            with open(pdfs[title], "rb") as fh:
                r = req(who, "POST", "/documents", loc=INSIDE,
                        data={"title": title, "doc_type": doc_type, "classification": cls, "tags": doc_type.lower()},
                        files={"file": (f"{pdfs[title].stem}.pdf", fh, "application/pdf")})
            if r.status_code != 201:
                sys.exit(f"STOP: upload of {title!r} returned {r.status_code}: {r.text[:300]}")
            doc = req("legal", "GET", f"/documents/{r.json()['document_id']}").json()
            print(f"  upload      -> {doc['status']}")
            if fresh_db and i == 0:
                # One real refusal, made for real: the same user, from outside the fence. Creates nothing.
                with open(pdfs[title], "rb") as fh:
                    d = req("staff", "POST", "/documents", loc=OUTSIDE,
                            data={"title": "Outside-fence attempt", "doc_type": "MEMO", "classification": "PUBLIC"},
                            files={"file": ("x.pdf", fh, "application/pdf")})
                print(f"  (one real outside-fence upload attempt as staff -> HTTP {d.status_code}, refused by the server)")
        else:
            print(f"  exists      -> {doc['status']}")
        final = advance(i, doc, row, anchors)
        want = {"CHANGES": "DRAFT"}.get(target, target)
        if final != want:
            print(f"  NOTE: ended at {final}, target was {want}")

    if chain_work:
        _, bal_after = wallet()
        print(f"[wallet] balance before {eth(bal_before)}\n[wallet] balance after  {eth(bal_after)}  "
              f"(spent {eth(bal_before - bal_after)})")
    for title, st, tx in anchors:
        print(f"[anchor] {title}: {st}  tx {tx}")


# ---------------------------------------------------------------------------------------------------- report
def table(title: str, counter: Counter) -> None:
    print(f"\n{title}")
    for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {k:<28}{v:>4}")
    print(f"  {'TOTAL':<28}{sum(counter.values()):>4}")


def report() -> None:
    docs = all_documents(include_archived=True)  # the default Repository/Dashboard list hides ARCHIVED
    table("Documents per status", Counter(d["status"] for d in docs))
    table("Documents per clearance", Counter(d["classification"] for d in docs))
    table("Documents per owner", Counter(d["owner_name"] for d in docs))
    print("\nTotals as each role sees them (Dashboard = list total; Repository = list total; Reports = sum of by-status):")
    for role in ("legal", "reviewer", "auditor", "staff", "admin"):
        total = req(role, "GET", "/documents", params={"limit": 1}).json()["total"]
        repo = len(all_documents(role))
        rep = ""
        if role in ("admin", "auditor"):
            s = req(role, "GET", "/reports/summary").json()
            rep = f"  reports={sum(x['count'] for x in s['documents_by_status'])}"
        print(f"  {role:<9} dashboard={total:<3} repository={repo:<3}{rep}")
    active = next((d for d in docs if d["status"] == "ACTIVE"), None)  # (docs includes ARCHIVED too)
    if active:
        v = req("legal", "POST", f"/verify/{active['current_version_id']}")
        j = v.json()
        print(f"\nVerification of ACTIVE document {active['title']!r}: HTTP {v.status_code} result={j.get('result')} "
              f"tx={j.get('tx_hash')}")
    h = _client.get("/blockchain/anchors/attention", headers={"Authorization": f"Bearer {login('admin')}"})
    print(f"Stuck-anchor list: HTTP {h.status_code} {h.text[:160]}")


if __name__ == "__main__":
    assert_backend_is_demo()
    if "--report" not in sys.argv:
        seed()
    report()
