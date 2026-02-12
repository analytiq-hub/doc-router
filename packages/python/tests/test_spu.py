"""Unit tests for SPU billing logic (compute_spu_to_charge, etc.)."""
import pytest
from unittest.mock import patch

import analytiq_data.payments.spu as spu_module


@pytest.mark.parametrize(
    "actual_cost,price_per_credit,expected",
    [
        (0, 0.05, 1),
        (0.0, 0.05, 1),
        (0.001, 0.05, 1),  # ceil(2 * 0.001 / 0.05) = 1
        (1.0, 0.05, 40),  # ceil(2 * 1.0 / 0.05) = 40
        (10.0, 0.05, 50),  # ceil(2 * 10 / 0.05) = 400 → capped at MAX_SPU_PER_LLM_CALL = 50
    ],
)
def test_compute_spu_to_charge_parametrized(actual_cost, price_per_credit, expected):
    """Parametrized cases for the core billing formula."""
    with patch.object(spu_module, "get_price_per_credit", return_value=price_per_credit):
        assert spu_module.compute_spu_to_charge(actual_cost) == expected


def test_compute_spu_to_charge_actual_cost_zero_returns_min_spu():
    """actual_cost=0 or None returns min_spu."""
    assert spu_module.compute_spu_to_charge(0) == 1
    assert spu_module.compute_spu_to_charge(0.0) == 1
    assert spu_module.compute_spu_to_charge(None) == 1
    assert spu_module.compute_spu_to_charge(-1) == 1


def test_compute_spu_to_charge_negative_returns_min_spu():
    """actual_cost < 0 returns min_spu."""
    assert spu_module.compute_spu_to_charge(-0.01) == 1


def test_compute_spu_to_charge_no_hook_returns_min_spu():
    """When get_price_per_credit hook is not set, returns min_spu."""
    with patch.object(spu_module, "get_price_per_credit", None):
        assert spu_module.compute_spu_to_charge(0.05) == 1
        assert spu_module.compute_spu_to_charge(1.0) == 1


def test_compute_spu_to_charge_hook_returns_zero_returns_min_spu():
    """When get_price_per_credit returns 0, returns min_spu."""
    with patch.object(spu_module, "get_price_per_credit", return_value=0):
        assert spu_module.compute_spu_to_charge(0.05) == 1
    with patch.object(spu_module, "get_price_per_credit", return_value=0.0):
        assert spu_module.compute_spu_to_charge(0.05) == 1


def test_compute_spu_to_charge_based_on_cost():
    """SPUs = ceil(200% * actual_cost / price_per_credit); at least 1."""
    # 0.05 at $0.05/SPU, 200%: 2 * 0.05 / 0.05 = 2 SPUs
    with patch.object(spu_module, "get_price_per_credit", return_value=0.05):
        assert spu_module.compute_spu_to_charge(0.05) == 2
        # 0.01 at $0.05/SPU, 200%: 2 * 0.01 / 0.05 = 0.4 -> ceil = 1
        assert spu_module.compute_spu_to_charge(0.01) == 1
        # 0.50 at $0.05/SPU, 200%: 2 * 0.50 / 0.05 = 20
        assert spu_module.compute_spu_to_charge(0.50) == 20


def test_compute_spu_to_charge_capped_at_max():
    """Result is capped at MAX_SPU_PER_LLM_CALL."""
    with patch.object(spu_module, "get_price_per_credit", return_value=0.0001):
        # 0.01 at $0.0001/SPU, 200%: 2 * 0.01 / 0.0001 = 200 -> capped at 50
        assert spu_module.compute_spu_to_charge(0.01) == 50
        assert spu_module.compute_spu_to_charge(1.0) == 50


def test_compute_spu_to_charge_very_small_price():
    """With small price_per_credit, still capped."""
    with patch.object(spu_module, "get_price_per_credit", return_value=0.00001):
        spus = spu_module.compute_spu_to_charge(1.0)
        assert spus == spu_module.MAX_SPU_PER_LLM_CALL
        assert spus == 50


def test_compute_spu_to_charge_min_spu_override():
    """min_spu parameter is respected."""
    with patch.object(spu_module, "get_price_per_credit", return_value=0.05):
        assert spu_module.compute_spu_to_charge(0.05, min_spu=3) == 3  # 2 would be computed, min 3 wins
        assert spu_module.compute_spu_to_charge(0.50, min_spu=5) == 20  # 20 > 5
