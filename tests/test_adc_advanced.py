"""Advanced ADC median filter tests (REQ-002).

Exercises window semantics, reset behaviour, mathematical properties,
float precision, large sample streams, and edge-case sequences.
"""

from __future__ import annotations

from ismart_core.sensor.adc import MedianFilter, _median

# ---------------------------------------------------------------------------
# Window fill behaviour
# ---------------------------------------------------------------------------


def test_window_fills_at_exactly_5():
    """Filter returns None for first 4 pushes and a value on the 5th."""
    filt = MedianFilter()
    results = [filt.push(float(i)) for i in range(1, 6)]
    assert results[:4] == [None, None, None, None]
    assert results[4] is not None


def test_returns_median_not_mean():
    """Median of [1, 1, 1, 1, 100] is 1.0, not 20.8."""
    filt = MedianFilter()
    for v in [1.0, 1.0, 1.0, 1.0]:
        filt.push(v)
    result = filt.push(100.0)
    assert result == 1.0, f"Expected 1.0 (median), got {result}"


def test_ascending_sequence_median():
    """Median of [1, 2, 3, 4, 5] = 3.0."""
    filt = MedianFilter()
    for v in [1.0, 2.0, 3.0, 4.0]:
        filt.push(v)
    result = filt.push(5.0)
    assert result == 3.0


def test_descending_sequence_median():
    """Median of [5, 4, 3, 2, 1] = 3.0."""
    filt = MedianFilter()
    for v in [5.0, 4.0, 3.0, 2.0]:
        filt.push(v)
    result = filt.push(1.0)
    assert result == 3.0


def test_uniform_sequence_median():
    """Median of [7, 7, 7, 7, 7] = 7.0."""
    filt = MedianFilter()
    for _ in range(4):
        filt.push(7.0)
    result = filt.push(7.0)
    assert result == 7.0


def test_spike_rejection():
    """A single spike in an otherwise uniform signal is rejected."""
    filt = MedianFilter()
    # Fill window with baseline
    for _ in range(4):
        filt.push(10.0)
    # Spike
    result = filt.push(9999.0)
    # Median of [10, 10, 10, 10, 9999] = 10.0
    assert result == 10.0


def test_dip_rejection():
    """A single dip in an otherwise uniform signal is rejected."""
    filt = MedianFilter()
    for _ in range(4):
        filt.push(50.0)
    result = filt.push(-9999.0)
    # Median of [50, 50, 50, 50, -9999] = 50.0
    assert result == 50.0


# ---------------------------------------------------------------------------
# Sliding window behaviour
# ---------------------------------------------------------------------------


def test_window_slides_correctly():
    """After the window fills, values slide correctly (oldest drops out)."""
    filt = MedianFilter()
    # Fill: [1, 2, 3, 4, 5] → median 3
    for v in [1.0, 2.0, 3.0, 4.0]:
        filt.push(v)
    assert filt.push(5.0) == 3.0
    # Slide: [2, 3, 4, 5, 6] → median 4
    assert filt.push(6.0) == 4.0
    # Slide: [3, 4, 5, 6, 7] → median 5
    assert filt.push(7.0) == 5.0


def test_window_evicts_oldest():
    """A spike added 5 steps ago no longer affects the median."""
    filt = MedianFilter()
    # Inject spike first
    filt.push(9999.0)
    # Fill with baseline
    for _ in range(3):
        filt.push(1.0)
    filt.push(1.0)  # window: [9999, 1, 1, 1, 1] → median 1.0
    # Push one more; window becomes [1, 1, 1, 1, 1] — spike evicted
    result = filt.push(1.0)
    assert result == 1.0


def test_100_samples_produces_100_minus_4_outputs():
    """For N samples, (N-4) non-None results are produced."""
    filt = MedianFilter()
    results = [filt.push(float(i)) for i in range(100)]
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 96  # 100 - (WINDOW - 1)


# ---------------------------------------------------------------------------
# Reset behaviour
# ---------------------------------------------------------------------------


def test_reset_clears_buffer():
    """After reset(), the filter behaves as if freshly constructed."""
    filt = MedianFilter()
    for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
        filt.push(v)
    filt.reset()
    # Should return None for next 4 values
    for v in [10.0, 20.0, 30.0, 40.0]:
        assert filt.push(v) is None
    result = filt.push(50.0)
    assert result is not None


def test_reset_then_correct_median():
    """After reset, correct median is produced for the new window."""
    filt = MedianFilter()
    for v in [100.0, 200.0, 300.0, 400.0, 500.0]:
        filt.push(v)
    filt.reset()
    for v in [2.0, 4.0, 6.0, 8.0]:
        filt.push(v)
    result = filt.push(10.0)
    # Median of [2, 4, 6, 8, 10] = 6.0
    assert result == 6.0


def test_multiple_resets():
    """Multiple reset() calls are idempotent."""
    filt = MedianFilter()
    for _ in range(3):
        filt.reset()
    for v in [5.0, 10.0, 15.0, 20.0]:
        filt.push(v)
    result = filt.push(25.0)
    assert result == 15.0


# ---------------------------------------------------------------------------
# Float precision
# ---------------------------------------------------------------------------


def test_float_precision_small_values():
    """Filter handles sub-unit floats without significant precision loss."""
    filt = MedianFilter()
    samples = [0.001, 0.002, 0.003, 0.004, 0.005]
    for v in samples[:-1]:
        filt.push(v)
    result = filt.push(samples[-1])
    assert abs(result - 0.003) < 1e-10


def test_negative_values():
    """Filter works correctly with all-negative samples."""
    filt = MedianFilter()
    for v in [-5.0, -4.0, -3.0, -2.0]:
        filt.push(v)
    result = filt.push(-1.0)
    # Median of [-5, -4, -3, -2, -1] = -3.0
    assert result == -3.0


def test_mixed_sign_values():
    """Filter works with mixed positive and negative samples."""
    filt = MedianFilter()
    for v in [-2.0, -1.0, 0.0, 1.0]:
        filt.push(v)
    result = filt.push(2.0)
    # Median of [-2, -1, 0, 1, 2] = 0.0
    assert result == 0.0


def test_large_values():
    """Filter handles large floating point values without overflow."""
    filt = MedianFilter()
    large = 1e15
    for _ in range(4):
        filt.push(large)
    result = filt.push(large)
    assert result == large


# ---------------------------------------------------------------------------
# _median helper tests
# ---------------------------------------------------------------------------


def test_median_single_element():
    assert _median([42.0]) == 42.0


def test_median_two_elements():
    assert _median([1.0, 3.0]) == 2.0


def test_median_three_elements_odd_count():
    assert _median([3.0, 1.0, 2.0]) == 2.0


def test_median_already_sorted():
    assert _median([1.0, 2.0, 3.0, 4.0, 5.0]) == 3.0


def test_median_reverse_sorted():
    assert _median([5.0, 4.0, 3.0, 2.0, 1.0]) == 3.0


def test_median_all_equal():
    assert _median([7.0] * 10) == 7.0


def test_median_floating_precision():
    result = _median([1.1, 2.2, 3.3, 4.4, 5.5])
    assert abs(result - 3.3) < 1e-10
