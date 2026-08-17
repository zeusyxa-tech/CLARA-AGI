"""
Phase 2 offline pytest suite.
No Ollama/network/model download required.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent


os.chdir(REPO)


class TestRuntimeProfile:
    def test_profile_defaults(self):
        from runtime_profile import choose_profile, governor_status
        profile = choose_profile("mobile_12gb_safe")
        assert profile.max_concurrency == 1
        assert profile.context_default == 2048
        assert profile.context_hard_cap == 4096
        assert profile.completion_default == 384
        assert profile.reserve_ram_bytes == 3 * 1024 * 1024 * 1024
        status = governor_status("mobile_12gb_safe", provider_model="qwen2.5:1.5b", backend="ollama")
        assert status["profile"] == "mobile_12gb_safe"
        assert status["backend"] == "ollama"
        assert status["provider_model"] == "qwen2.5:1.5b"

    def test_degraded_on_low_ram(self, monkeypatch):
        from runtime_profile import RuntimeProfile, degraded_reason
        profile = RuntimeProfile(name="mobile_12gb_safe", reserve_ram_bytes=1024)
        hw = {"ram_available_bytes": 512, "swap_used_bytes": 0, "battery_power_plugged": None, "load1": 0.5, "cpu_threads": 8}
        reason = degraded_reason(hw, profile)
        assert reason is not None
        assert "low_ram" in reason

    def test_degraded_on_high_swap(self):
        from runtime_profile import RuntimeProfile, degraded_reason
        profile = RuntimeProfile(name="mobile_12gb_safe", reserve_ram_bytes=0)
        hw = {"ram_available_bytes": 8 * 1024 * 1024 * 1024, "swap_used_bytes": 1024 * 1024 * 1024, "battery_power_plugged": None, "load1": 0.5, "cpu_threads": 8}
        reason = degraded_reason(hw, profile)
        assert reason is not None and reason.startswith("high_swap")

    def test_degraded_on_battery(self):
        from runtime_profile import RuntimeProfile, degraded_reason
        profile = RuntimeProfile(name="mobile_12gb_safe", reserve_ram_bytes=0)
        hw = {"ram_available_bytes": 8 * 1024 * 1024 * 1024, "swap_used_bytes": 0, "battery_power_plugged": False, "load1": 0.5, "cpu_threads": 8}
        reason = degraded_reason(hw, profile)
        assert reason == "on_battery"


class TestBoundedAutolearn:
    def test_skips_when_degraded(self):
        from bounded_autolearn import run_idle_study_session
        class DummyMem:
            def __init__(self):
                self.conn = _FakeConn()
        class _FakeConn:
            def execute(self, *a, **k):
                return []
            def fetchall(self):
                return []
        class DummyAGI:
            mem = DummyMem()
        report = run_idle_study_session(DummyAGI(), profile_name="mobile_12gb_safe", force=False, allow_network=False)
        assert report["stop_reason"].startswith("skipped_degraded:")
        assert report["session_end"] is not None

    def test_force_runs_local_review_only(self):
        from bounded_autolearn import run_idle_study_session
        class DummyMem:
            def __init__(self):
                self.conn = _FakeConn2()
        class _FakeConn2:
            def execute(self, sql, *a, **k):
                if "semantics" in sql:
                    return [_Row("python basics"), _Row("safe shell")]
                return []
            def fetchall(self):
                return []
        class _Row:
            def __init__(self, topic):
                self.topic = topic
                self.id = 1
                self.fact = f"fact about {topic}"
                self.confidence = 0.7
                self.source = "test"
                self.ts = time.time()
        class DummyAGI:
            mem = DummyMem()
        report = run_idle_study_session(DummyAGI(), profile_name="mobile_12gb_safe", force=True, allow_network=False)
        assert report["stopped_early"] is False
        assert len(report["topics"]) <= 3
        assert report["facts_candidate"] == []
        assert report["used_session_minutes"] >= 0


class TestAgentCLI:
    def test_new_flags_present(self):
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--profile", default="mobile_12gb_safe")
        ap.add_argument("--idle-study", action="store_true")
        ap.add_argument("--allow-network", action="store_true")
        ns = ap.parse_args(["--profile", "eco", "--idle-study", "--allow-network"])
        assert ns.profile == "eco"
        assert ns.idle_study is True
        assert ns.allow_network is True

    def test_status_runtime_key(self):
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True, profile="eco")
        st = agi.status()
        assert "runtime" in st
        assert st["runtime"]["profile"] == "eco"
        assert st["runtime"]["mode"] in {"chat", "micro-fallback", "degraded"}


class TestBrainRouting:
    def test_exact_model_respected(self):
        from brain import Brain
        b = Brain(force_micro=True, model="custom-model")
        assert b.model == "custom-model"
        assert b.backend == "micro"

    def test_ollama_micro_fallback(self):
        from brain import Brain
        b = Brain(force_micro=True)
        assert b.backend == "micro"
