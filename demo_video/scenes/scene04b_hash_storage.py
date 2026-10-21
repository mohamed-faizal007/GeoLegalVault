"""Scene 4b: where the SHA-256 is visible in the UI (Version History) and what is in the private bucket."""
from common import *
import supp


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "staff", INSIDE)
    sc.say(p, "Authorized Staff opens Version History for the uploaded document")
    sc.login(p, "staff")
    p.goto(f"{APP}/documents/{st['doc_id']}/versions")
    p.wait_for_timeout(3000)
    sc.say(p, "Version 1: the SHA-256 fingerprint of the file (shortened on screen), status SUBMITTED",
           "SHA-256 turns any file into a 64-character fingerprint. Change one byte and the fingerprint changes completely.")
    p.wait_for_timeout(7000)
    d = db()
    v = d.document_versions.find_one({"document_id": __import__("bson").ObjectId(st["doc_id"])})
    save_state(sha_v1=v["sha256"], version_id=str(v["_id"]), storage_key=v["storage_key"])
    sc.say(p, "Supplementary view: the object in the private bucket")
    show_text(p, "Private bucket: the file is stored under a server-made key, not its filename",
              supp.bucket_listing(st["doc_id"]) + "\n\n" + supp._j(supp.storage_head(v["storage_key"])) +
              "\n\nThe key is docs/<documentId>/v<version>-<sha256>. The bucket is private; downloads use a pre-signed link that expires in 60 s.")
    p.wait_for_timeout(12000)


run_scene("scene04b_hash_storage", "Scene 4b - Fingerprint and storage", main)
