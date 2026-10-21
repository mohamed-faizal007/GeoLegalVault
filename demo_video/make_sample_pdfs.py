"""Create the two sample legal PDFs used by the demo (placeholder text only, no real parties).

Run with the demo_video venv:  demo_video/.venv/Scripts/python.exe demo_video/make_sample_pdfs.py
Output: demo_video/samples/DEMO_Lease_Agreement_v1.pdf and ..._v2.pdf (v2 changes one clause).
The tampered copy is NOT made here: demo/tamper.py changes a byte of the stored object itself.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).parent / "samples"

CLAUSES = {
    "v1": "4.2 Monthly rent is INR 25,000, payable on or before the 5th day of each month.",
    "v2": "4.2 Monthly rent is INR 27,500, payable on or before the 5th day of each month.",
}


def build(version: str) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / f"DEMO_Lease_Agreement_{version}.pdf"
    styles = getSampleStyleSheet()
    body = [
        Paragraph("SAMPLE LEASE AGREEMENT (DEMONSTRATION ONLY)", styles["Title"]),
        Paragraph(
            "This is a made-up document for a software demonstration. The parties, amounts and "
            "terms are fictional and have no legal effect.",
            styles["Normal"],
        ),
        Spacer(1, 14),
        Paragraph("1. Parties: Example Landlord Pvt Ltd and Example Tenant Co.", styles["Normal"]),
        Paragraph("2. Premises: Unit 12, Sample Business Park, Salem.", styles["Normal"]),
        Paragraph("3. Term: 11 months from the date of signing.", styles["Normal"]),
        Paragraph(CLAUSES[version], styles["Normal"]),
        Paragraph("5. Either party may end this agreement with 30 days written notice.", styles["Normal"]),
        Spacer(1, 14),
        Paragraph(f"Document revision: {version}", styles["Italic"]),
    ]
    # invariant=1 + fixed creation date makes the file bytes reproducible.
    SimpleDocTemplate(str(path), pagesize=A4, invariant=1, title=f"Sample Lease {version}").build(body)
    return path


if __name__ == "__main__":
    for v in ("v1", "v2"):
        print(build(v))
