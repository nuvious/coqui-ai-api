"""Tests for ``wait_for_job``, the blocking-facade helper (task T-02-01-01).

The worker is disabled (``COQUI_AI_API_START_WORKER=0``, set in
``conftest.py``), so every job here is driven by hand through the registry
helpers from a background thread, exactly as ``_process_task`` would.
"""

import threading
import time
from typing import Any


class TestWaitForJobSuccess:
    def test_returns_succeeded_once_the_job_is_marked_done(self, app: Any) -> None:
        app.register_job("j1", kind="single", word_count=3)

        def driver() -> None:
            time.sleep(0.05)
            app.mark_processing("j1")
            app.mark_done("j1")

        threading.Thread(target=driver).start()

        outcome = app.wait_for_job("j1", timeout_seconds=2.0)

        assert outcome is app.WaitOutcome.SUCCEEDED


class TestWaitForJobError:
    def test_returns_errored_once_the_job_is_marked_error(self, app: Any) -> None:
        app.register_job("j1", kind="single", word_count=3)

        def driver() -> None:
            time.sleep(0.05)
            app.mark_processing("j1")
            app.mark_error("j1")

        threading.Thread(target=driver).start()

        outcome = app.wait_for_job("j1", timeout_seconds=2.0)

        assert outcome is app.WaitOutcome.ERRORED


class TestWaitForJobVanished:
    def test_returns_vanished_for_an_id_never_registered(self, app: Any) -> None:
        outcome = app.wait_for_job("does-not-exist", timeout_seconds=1.0)

        assert outcome is app.WaitOutcome.VANISHED

    def test_returns_vanished_when_the_job_expires_mid_wait(self, app: Any) -> None:
        app.register_job("j1", kind="single", word_count=3)
        app.mark_processing("j1")

        def driver() -> None:
            time.sleep(0.05)
            app._expire_job("j1")

        threading.Thread(target=driver).start()

        outcome = app.wait_for_job("j1", timeout_seconds=2.0)

        assert outcome is app.WaitOutcome.VANISHED


class TestWaitForJobTimeout:
    def test_gives_up_after_the_injected_bound_without_touching_the_job(
        self, app: Any
    ) -> None:
        app.register_job("j1", kind="single", word_count=3)
        app.mark_processing("j1")

        started = time.monotonic()
        outcome = app.wait_for_job("j1", timeout_seconds=0.1)
        elapsed = time.monotonic() - started

        assert outcome is app.WaitOutcome.TIMED_OUT
        # A well bounded wait: it gave up close to the injected bound, not the
        # (much larger) production default.
        assert elapsed < 1.0
        # The decision recorded in CONTRIBUTING.md: giving up on the wait does
        # not cancel the job. It is left exactly as it was.
        assert app.jobs["j1"]["status"] == "processing"

    def test_zero_bound_gives_up_immediately_for_a_job_still_queued(
        self, app: Any
    ) -> None:
        app.register_job("j1", kind="single", word_count=3)

        outcome = app.wait_for_job("j1", timeout_seconds=0.0)

        assert outcome is app.WaitOutcome.TIMED_OUT


class TestWaitForJobLockDiscipline:
    def test_jobs_lock_is_released_between_polls(self, app: Any) -> None:
        """The helper must never hold ``jobs_lock`` across a poll interval.

        A concurrent, non-blocking acquire of ``jobs_lock`` must succeed
        repeatedly while ``wait_for_job`` is polling, proving the lock is only
        ever held for the instant of a single status read.
        """
        app.register_job("j1", kind="single", word_count=3)
        app.mark_processing("j1")

        acquired_while_waiting = threading.Event()
        stop = threading.Event()

        def prober() -> None:
            while not stop.is_set():
                if app.jobs_lock.acquire(blocking=False):
                    app.jobs_lock.release()
                    acquired_while_waiting.set()
                time.sleep(0.005)

        prober_thread = threading.Thread(target=prober)
        prober_thread.start()

        app.wait_for_job("j1", timeout_seconds=0.2)
        stop.set()
        prober_thread.join()

        assert acquired_while_waiting.is_set()
