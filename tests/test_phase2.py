"""
Phase 2 offline pytest suite.
No Ollama/network/model download required.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent

os.chdir(REPO)

import tempfile

_TMP_FIXTURE = tempfile.TemporaryDirectory()
os.environ["CLARA_DB_DIR"] = _TMP_FIXTURE.name
os.environ["CLARA_DB_PATH"] = str(Path(_TMP_FIXTURE.name) / "clara.db")
os.environ["CLARA_OLLAMA_URL"] = "http://127.0.0.1:11434"


def _ensure_language_column():
    db = os.environ["CLARA_DB_PATH"]
    try:
        with sqlite3.connect(db, check_same_thread=False) as conn:
            conn.execute("ALTER TABLE semantics ADD COLUMN language TEXT DEFAULT 'vi'")
            conn.commit()
    except Exception:
        pass


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
    def test_skips_when_degraded(self, tmp_path, monkeypatch):
        from bounded_autolearn import run_idle_study_session
        monkeypatch.setattr("bounded_autolearn.REPORT_DIR", tmp_path)
        monkeypatch.setattr("bounded_autolearn.probe_hardware", lambda: {
            "ram_available_bytes": 0,
            "swap_used_bytes": 0,
            "battery_power_plugged": False,
            "load1": 0.5,
            "cpu_threads": 8,
        })

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
        assert report["stop_reason"] is not None
        assert report["stop_reason"].startswith("skipped_degraded:")
        assert report["session_end"] is not None

    def test_force_runs_local_review_only(self, tmp_path, monkeypatch):
        from bounded_autolearn import run_idle_study_session
        monkeypatch.setattr("bounded_autolearn.REPORT_DIR", tmp_path)
        monkeypatch.setattr("bounded_autolearn.probe_hardware", lambda: {
            "ram_available_bytes": 8 * 1024 * 1024 * 1024,
            "swap_used_bytes": 0,
            "battery_power_plugged": True,
            "load1": 0.5,
            "cpu_threads": 12,
        })

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

    def test_status_runtime_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True, profile="eco")
        st = agi.status()
        assert "runtime" in st
        assert st["runtime"]["profile"] == "eco"
        assert st["runtime"]["mode"] in {"chat", "micro-fallback", "degraded"}


class TestBrainRouting:
    def test_exact_model_respected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from brain import Brain
        b = Brain(force_micro=True, model="custom-model")
        assert b.model == "custom-model"
        assert b.backend == "micro"

    def test_ollama_micro_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from brain import Brain
        b = Brain(force_micro=True)
        assert b.backend == "micro"

    def test_language_env_affects_brain(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        monkeypatch.setenv("CLARA_LANGUAGE", "en")
        from brain import Brain
        b = Brain(force_micro=True)
        assert b.language == "en"
        assert "CLARA-AGI" in b._tag_to_system("__ANSWER__")

    def test_vi_prompts_keep_markers(self):
        from prompts_vi import system_for
        text = system_for("__PLAN__", language="vi")
        assert "JSON" in text
        assert "tool_name" in text
        assert "steps" in text

    def test_native_chat_uses_message_content(self, monkeypatch):
        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

            def close(self):
                return None

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url if hasattr(req, "full_url") else getattr(req, "full_url", None)
            data = json.loads(req.data.decode())
            captured["messages"] = data.get("messages", [])
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        from brain import ollama_chat_messages
        out = ollama_chat_messages([{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}], model="m", url="http://x")
        assert out == "ok"
        assert captured["messages"][1]["content"] == "hello"


class TestLocaleDefaults:
    def test_default_language_is_vi(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True)
        assert agi.language == "vi"
        assert agi.brain.language == "vi"
        assert agi.status()["brain"]["language"] == "vi"

    def test_language_flag_and_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        monkeypatch.setenv("CLARA_LANGUAGE", "en")
        from brain import Brain
        b = Brain(force_micro=True, language="en")
        assert b.language == "en"

    def test_user_message_not_lost_on_overflow(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True)
        for i in range(20):
            agi.wm.append({"role": "user", "content": f"x{i}"})
            agi.wm.append({"role": "assistant", "content": "y"})
        agi.wm.append({"role": "user", "content": "current message"})
        wm = agi._compact_wm()
        assert any(i.get("content") == "current message" for i in wm)

    def test_unicode_nfc_and_no_diacritic_query(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        _ensure_language_column()
        import memory as memory_module
        importlib.reload(memory_module)
        from memory import Memory
        mem = Memory()
        mem.learn("test", "Hà Nội có mùa thu đẹp.", confidence=0.8, language="vi")
        hits = mem.recall_semantics("Ha Noi", limit=5)
        assert any("Hà Nội" in (h.get("fact") or "") for h in hits)

    def test_code_block_not_translated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True)
        text = "Chạy: python main.py --help | grep language"
        assert "python main.py --help" in text

    def test_language_feedback_flow(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True)
        out = agi.chat("góp ý ngôn ngữ: dùng từ 'rất vui' thay vì 'vui vẻ'")
        assert "✅" in out
        cands = agi.mem.review_candidates(limit=5)
        assert any(c.get("source") == "user_language_feedback" for c in cands)

    def test_benchmark_fail_closed_without_ollama(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLARA_OLLAMA_URL", raising=False)
        from benchmark import run_benchmark
        report = run_benchmark("missing-model", backend="ollama")
        assert report["recommendation"] == "unavailable"
        assert report["backend"] == "micro"
        assert report["results"] == []

    def test_no_scheduler_background_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True)
        study = getattr(agi, "_study", None)
        assert study is None or getattr(study, "_running", False) is False

    def test_idle_study_writes_report_under_tmp(self, tmp_path, monkeypatch):
        from bounded_autolearn import run_idle_study_session
        monkeypatch.setattr("bounded_autolearn.REPORT_DIR", tmp_path)
        monkeypatch.setattr("bounded_autolearn.probe_hardware", lambda: {
            "ram_available_bytes": 8 * 1024 * 1024 * 1024,
            "swap_used_bytes": 0,
            "battery_power_plugged": True,
            "load1": 0.5,
            "cpu_threads": 12,
        })

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

        report = run_idle_study_session(DummyAGI(), profile_name="mobile_12gb_safe", force=True, allow_network=False)
        assert report["stop_reason"] is None
        assert report["session_end"] is not None
        reports = list(tmp_path.glob("idle_study_*.json"))
        assert reports
        assert all(str(r).startswith(str(tmp_path)) for r in reports)
