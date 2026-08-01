"""Thread-safe estimator that learns TTS generation time from completed jobs.

Standard-library only (no ``torch``/``TTS``) so it stays cheap to import.
"""

import os
import threading

SEED_OVERHEAD = float(os.getenv("SEED_OVERHEAD", "3.0"))
SEED_PER_WORD = float(os.getenv("SEED_PER_WORD", "0.3"))


class RateEstimator:
    """Learns ``duration ~= overhead + per_word * words`` from completed jobs.

    With zero samples, falls back to seed constants. With one sample (or
    multiple samples that all share the same word count), falls back to a
    cumulative average seconds/word. Once at least two distinct word counts
    have been observed, upgrades to an ordinary-least-squares linear fit,
    maintained incrementally in O(1) per ``record`` call.
    """

    def __init__(
        self, seed_overhead: float = SEED_OVERHEAD, seed_per_word: float = SEED_PER_WORD
    ):
        self._seed_overhead = seed_overhead
        self._seed_per_word = seed_per_word
        self._lock = threading.Lock()
        self._n = 0
        self._sum_w = 0.0
        self._sum_w2 = 0.0
        self._sum_d = 0.0
        self._sum_wd = 0.0
        self._distinct_words: set[float] = set()

    def record(self, words: int, duration: float) -> None:
        """Ingest one completed job's word count and observed duration."""
        words = max(words, 0)
        duration = max(duration, 0.0)
        with self._lock:
            self._n += 1
            self._sum_w += words
            self._sum_w2 += words * words
            self._sum_d += duration
            self._sum_wd += words * duration
            self._distinct_words.add(words)

    def predict(self, words: int) -> float:
        """Estimate the number of seconds needed to synthesise ``words``."""
        words = max(words, 0)
        with self._lock:
            n = self._n
            sum_w = self._sum_w
            sum_w2 = self._sum_w2
            sum_d = self._sum_d
            sum_wd = self._sum_wd
            distinct = len(self._distinct_words)

        if n == 0:
            return max(self._seed_overhead + self._seed_per_word * words, 0.0)

        if distinct >= 2:
            denominator = n * sum_w2 - sum_w * sum_w
            if abs(denominator) > 1e-9:
                per_word = (n * sum_wd - sum_w * sum_d) / denominator
                overhead = (sum_d - per_word * sum_w) / n
                per_word = max(per_word, 0.0)
                overhead = max(overhead, 0.0)
                return max(overhead + per_word * words, 0.0)

        if sum_w > 0:
            return max((sum_d / sum_w) * words, 0.0)

        return max(self._seed_overhead + self._seed_per_word * words, 0.0)
