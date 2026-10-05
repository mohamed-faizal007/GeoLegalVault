"""SEC-02 / D-051: the ordered levels and the visibility rule, with no database."""

import typing

import pytest

from app.core import clearance
from app.modules.users.schemas import ClearanceLevel


def test_the_schema_literal_is_the_same_set_as_the_levels():
    assert typing.get_args(ClearanceLevel) == clearance.LEVELS


def test_levels_are_ordered_lowest_first():
    assert clearance.LEVELS == ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET")
    ranks = [clearance.rank_of(level) for level in clearance.LEVELS]
    assert ranks == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("value", [None, "", "top_secret", "Top Secret", "SECRET", 3, ["PUBLIC"]])
def test_anything_that_is_not_a_level_has_no_rank(value):
    assert clearance.rank_of(value) is None


@pytest.mark.parametrize("user", [{}, {"clearance": None}, {"clearance": "GOD_MODE"}])
def test_a_missing_or_unknown_clearance_is_the_lowest(user):
    assert clearance.effective_clearance(user) == "PUBLIC"
    assert clearance.visible_classifications(user) == ["PUBLIC"]


def test_a_user_sees_their_own_level_and_everything_below_it_only():
    user = {"clearance": "CONFIDENTIAL"}
    assert clearance.visible_classifications(user) == ["PUBLIC", "INTERNAL", "CONFIDENTIAL"]
    assert clearance.can_see(user, "INTERNAL")
    assert clearance.can_see(user, "CONFIDENTIAL")
    assert not clearance.can_see(user, "RESTRICTED")
    assert not clearance.can_see(user, "TOP_SECRET")


@pytest.mark.parametrize("classification", [None, "", "restricted", "Top Secret", "UNKNOWN"])
def test_a_document_with_an_unrecognised_classification_is_visible_to_nobody(classification):
    top = {"clearance": "TOP_SECRET"}
    assert not clearance.can_see(top, classification)
