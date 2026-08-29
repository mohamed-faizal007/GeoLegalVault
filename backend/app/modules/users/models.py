"""users module Mongo collection + role enum."""

from enum import StrEnum

USERS_COLLECTION = "users"


class Role(StrEnum):
    ADMINISTRATOR = "ADMINISTRATOR"
    LEGAL_OFFICER = "LEGAL_OFFICER"
    REVIEWING_OFFICER = "REVIEWING_OFFICER"
    AUTHORIZED_STAFF = "AUTHORIZED_STAFF"
    AUDITOR = "AUDITOR"
