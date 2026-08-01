"""Tests for the standalone rate estimator (task 04)."""

import threading

import pytest

from coqui_ai_api.estimator import RateEstimator


class TestSeedPrediction:
    def test_zero_samples_uses_seed_formula(self):
        est = RateEstimator(seed_overhead=3.0, seed_per_word=0.3)
        assert est.predict(100) == pytest.approx(3.0 + 0.3 * 100)

    def test_zero_samples_zero_words(self):
        est = RateEstimator(seed_overhead=3.0, seed_per_word=0.3)
        assert est.predict(0) == pytest.approx(3.0)

    def test_seeds_overridable(self):
        est = RateEstimator(seed_overhead=1.0, seed_per_word=0.1)
        assert est.predict(50) == pytest.approx(1.0 + 0.1 * 50)


class TestCumulativeAverage:
    def test_single_sample_uses_cumulative_average(self):
        est = RateEstimator()
        est.record(words=50, duration=20.0)
        # 20s / 50 words = 0.4 s/word
        assert est.predict(100) == pytest.approx(40.0)

    def test_repeated_same_word_count_still_cumulative_average(self):
        est = RateEstimator()
        est.record(words=50, duration=20.0)
        est.record(words=50, duration=30.0)
        # total_duration=50, total_words=100 -> 0.5 s/word
        assert est.predict(50) == pytest.approx(25.0)


class TestLinearFit:
    def test_recovers_known_linear_relationship(self):
        overhead = 2.5
        per_word = 0.25
        est = RateEstimator()
        for words in (10, 40, 90, 150):
            duration = overhead + per_word * words
            est.record(words=words, duration=duration)

        for words in (20, 60, 120):
            expected = overhead + per_word * words
            assert est.predict(words) == pytest.approx(expected, rel=1e-6)

    def test_needs_at_least_two_distinct_word_counts(self):
        est = RateEstimator()
        est.record(words=50, duration=20.0)
        est.record(words=100, duration=40.0)
        # exactly matches a 0-overhead, 0.4 s/word line
        assert est.predict(200) == pytest.approx(80.0, rel=1e-6)


class TestClamping:
    def test_negative_words_and_duration_are_clamped(self):
        est = RateEstimator()
        est.record(words=-10, duration=-5.0)
        assert est.predict(-20) >= 0.0

    def test_prediction_never_negative_after_linear_fit(self):
        # A decreasing relationship (negative slope) should clamp per_word/overhead
        # to non-negative so predictions never go negative.
        est = RateEstimator()
        est.record(words=10, duration=50.0)
        est.record(words=1000, duration=1.0)
        assert est.predict(0) >= 0.0
        assert est.predict(1_000_000) >= 0.0

    def test_degenerate_denominator_falls_back_to_cumulative_average(self):
        # Same word count recorded repeatedly under different labels still
        # only counts as one distinct word count, so this stays on the
        # cumulative-average path rather than dividing by ~0.
        est = RateEstimator()
        est.record(words=50, duration=20.0)
        est.record(words=50, duration=20.0)
        assert est.predict(50) == pytest.approx(20.0)


class TestThreadSafety:
    def test_concurrent_records_do_not_corrupt_state(self):
        est = RateEstimator()
        n_threads = 8
        records_per_thread = 200

        def worker(word_base):
            for i in range(records_per_thread):
                est.record(words=word_base + i, duration=1.0)

        threads = [
            threading.Thread(target=worker, args=(t * 1000,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert est._n == n_threads * records_per_thread
        assert est.predict(10) >= 0.0
