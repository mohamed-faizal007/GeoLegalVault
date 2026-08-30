"""audit module Mongo collection.

`audit_logs` is append-only: this constant is used by the one insert call
site in `service.record()` and nowhere else. There is deliberately no
update/delete helper anywhere in this module.
"""

AUDIT_LOGS_COLLECTION = "audit_logs"
