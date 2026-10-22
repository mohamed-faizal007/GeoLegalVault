"""Scene 12: download the CURRENT version (V2). Geofenced, audited as ACCESS with the version id. The pre-signed URL is
captured by the harness (window.open is replaced in the page), used once to fetch and hash the bytes, and is NEVER
printed, logged, shown on screen or put in a caption. Denial shown here: outside the zone -> GEOFENCE_DENIED. (Below clearance -> 404 is scene12b.)
"""
import datetime as dt
import hashlib
import urllib.request

from common import *
import supp


def main(sc, browser):
    st = load_state()
    since = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    v1, v2 = supp.versions(st["doc_id"])
    assert v2["status"] == "ACTIVE" and v1["status"] == "SUPERSEDED"
    doc_url = f"{APP}/documents/{st['doc_id']}"

    staff = sc.context(browser, "staff", INSIDE)
    sc.login(staff, "staff")
    staff.goto(doc_url)
    staff.get_by_role("button", name="Download").wait_for()
    staff.evaluate("window.__opened = null")

    with sc.beat(staff, "k1", "Download gives the CURRENT version only (V2 now); it is geofenced", geo=True):
        staff.get_by_role("button", name="Download").hover()
    got = {}
    with sc.beat(staff, "k2", "The server answers with a short-lived pre-signed link (60 s); the API never streams the file", geo=True):
        staff.get_by_role("button", name="Download").click()
        staff.wait_for_function("() => !!window.__opened", timeout=30000)
        url = staff.evaluate("window.__opened")          # kept in memory only; never printed or shown
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read()
            got = dict(sha=hashlib.sha256(body).hexdigest(), size=len(body), ctype=r.headers.get("Content-Type"))
        except Exception as e:  # noqa: BLE001  (never let an exception message carry the signed URL into a log)
            raise RuntimeError(f"download fetch failed: {type(e).__name__}") from None
        finally:
            url = None
            staff.evaluate("window.__opened = null")
        staff.locator("main h1").first.hover()
    sample_sha = hashlib.sha256((VID / "samples" / "DEMO_Lease_v2.pdf").read_bytes()).hexdigest()
    fname = f"v2-{v2['sha256']}"
    with sc.beat(staff, "k3", "Supplementary view: the downloaded bytes hash to the recorded SHA-256 of V2 (the link is not shown)"):
        show_supp(staff, "Download check: hash of the downloaded file vs the recorded hash",
                  [f"file name (object):             {fname}",
                   f"downloaded:                     {got['size']} bytes, {got['ctype']}", "",
                   f"sha256 of downloaded bytes:     {got['sha']}",
                   f"recorded sha256 (V2, database): {v2['sha256']}", "",
                   "downloaded == recorded  ->  MATCH" if got["sha"] == v2["sha256"] else "downloaded != recorded  ->  DIFFERENT",
                   "downloaded == the V2 sample file that was uploaded: " + str(got["sha"] == sample_sha),
                   "", "(the pre-signed link itself is deliberately not shown)"],
                  highlight=[got["sha"], "MATCH"])
        assert got["sha"] == v2["sha256"], "downloaded bytes do not match the recorded hash"
    with sc.beat(staff, "k4", "Supplementary view: the download is audited as ACCESS, with the version id"):
        show_supp(staff, "audit_logs: the ACCESS row for this download",
                  supp.audit_lines(document_id=st["doc_id"], actions=["ACCESS"], limit=2, since=since),
                  highlight=["ACCESS", str(v2["_id"])],
                  note="meta.version_id is the version that was served: the current one (V2).")
    staff.goto(doc_url)
    staff.get_by_role("button", name="Download").wait_for()
    sc.set_geo("staff", OUTSIDE)
    with sc.beat(staff, "k5", "From OUTSIDE the zone the same Download button is refused: GEOFENCE_DENIED", geo=True):
        staff.get_by_role("button", name="Download").click()
        staff.locator("main").get_by_text("GEOFENCE_DENIED").first.wait_for()
        staff.locator("main").get_by_text("GEOFENCE_DENIED").first.hover()
    assert not staff.evaluate("window.__opened"), "a download was served from outside the zone"
    sc.close_role("staff")


run_scene("scene12_download", "Scene 12 - Download the current version", "s12", main)
