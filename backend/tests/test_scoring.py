"""Deterministic scoring: fixed weights, clamping, rounding, bounds."""
import pytest

from app.services.scoring_service import (
    WEIGHT_CONTENT,
    WEIGHT_CREATOR_FIT,
    WEIGHT_GEO_SEARCH,
    WEIGHT_TOPIC,
    calculate_relevance_score,
    clamp,
)


def test_weights_sum_to_one():
    assert WEIGHT_GEO_SEARCH + WEIGHT_TOPIC + WEIGHT_CONTENT + WEIGHT_CREATOR_FIT == pytest.approx(1.0)


def test_all_zero_is_zero():
    assert calculate_relevance_score(0, 0, 0, 0) == 0


def test_all_hundred_is_hundred():
    assert calculate_relevance_score(100, 100, 100, 100) == 100


def test_known_weighted_case():
    # 95*.35 + 90*.30 + 84*.25 + 88*.10 = 33.25 + 27 + 21 + 8.8 = 90.05 -> 90
    assert calculate_relevance_score(95, 90, 84, 88) == 90


def test_second_known_case():
    # 96*.35 + 90*.30 + 87*.25 + 91*.10 = 33.6 + 27 + 21.75 + 9.1 = 91.45 -> 91
    assert calculate_relevance_score(96, 90, 87, 91) == 91


def test_never_exceeds_100_even_with_out_of_range_inputs():
    assert calculate_relevance_score(200, 200, 200, 200) == 100


def test_negative_inputs_clamped_to_zero():
    assert calculate_relevance_score(-50, -10, -100, -1) == 0


def test_non_numeric_inputs_do_not_crash():
    assert calculate_relevance_score("bad", None, float("nan"), 50) == 5  # only fit contributes: 50*.10


@pytest.mark.parametrize("value,expected", [(-1, 0.0), (0, 0.0), (50, 50.0), (100, 100.0), (150, 100.0)])
def test_clamp(value, expected):
    assert clamp(value) == expected


def test_geo_weight_dominates():
    high_geo = calculate_relevance_score(100, 0, 0, 0)
    high_fit = calculate_relevance_score(0, 0, 0, 100)
    assert high_geo == 35
    assert high_fit == 10
    assert high_geo > high_fit
