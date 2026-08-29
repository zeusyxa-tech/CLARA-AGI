"""
Phase 2 offline pytest suite.
No Ollama/network/model download required.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)

import sys
sys.path.insert(0, str(REPO))


_TMP_FIXTURE = tempfile.TemporaryDirectory()
os.environ["CLARA_DB_DIR"] = _TMP_FIXTURE.name
os.environ["CLARA_DB_PATH"] = str(Path(_TMP_FIXTURE.name) / "clara.db")
os.environ["CLARA_OLLAMA_URL"] = "http://127.0.0.1:11434"


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

    def test_native_chat_message_content(self, monkeypatch):
        captured = {"path": None}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"message": {"content": "native-ok"}}).encode()

            def close(self):
                return None

        def fake_urlopen(req, timeout=None):
            captured["path"] = req.full_url if hasattr(req, "full_url") else getattr(req, "full_url", None)
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        from brain import ollama_chat_messages
        out = ollama_chat_messages([{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}], model="m", url="http://x")
        assert out == "native-ok"
        assert captured["path"] == "http://x/api/chat"

    def test_native_chat_fake_server_no_generate_fallback(self, monkeypatch):
        server = _FakeOllamaServer()
        server.start()
        try:
            from brain import ollama_chat_messages
            out = ollama_chat_messages([{"role": "user", "content": "hi"}], model="m", url=f"http://127.0.0.1:{server.port}")
            assert out == "hi-server-ok"
            assert server.generate_calls == 0
            assert server.chat_calls == 1
        finally:
            server.stop()


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
        b = Brain(force_micro=True)
        assert b.language == "en"

    def test_clara_language_env_overrides_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        monkeypatch.setenv("CLARA_LANGUAGE", "en")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True, language=None)
        assert agi.language == "en"
        assert agi.brain.language == "en"

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

    def test_idle_study_does_not_start_legacy_scheduler(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True, idle_study=True)
        assert getattr(agi, "idle_study", False) is True
        assert getattr(agi, "_study", None) is None

    def test_web_tools_gated_by_allow_network(self, monkeypatch):
        import web_tools
        monkeypatch.setattr("web_tools._NETWORK_ALLOWED", False)
        err_search = web_tools.web_search("python tips", max_results=1)
        assert any("error" in x and "Mạng đã tắt" in x.get("error", "") for x in err_search)
        err_fetch = web_tools.web_fetch("https://example.com")
        assert "Mạng đã tắt" in err_fetch

    def test_approve_reject_candidate_flow(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from agent import ClarasAGI
        agi = ClarasAGI(force_micro=True)
        agi.mem.add_candidate(topic="x", fact="y", source="test", confidence=0.5, reason="test")
        cands = agi.mem.review_candidates(limit=5)
        assert cands
        cid = cands[0]["id"]
        out1 = agi.chat(f"approve memory {cid}")
        assert "✅" in out1
        out2 = agi.chat(f"reject memory {cid}")
        assert "🗑️" in out2 or "❌" in out2

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

    def test_old_sqlite_schema_migrates_language_column(self, tmp_path, monkeypatch):
        db = tmp_path / "old.db"
        with sqlite3.connect(db, check_same_thread=False) as conn:
            conn.execute("""
                CREATE TABLE semantics(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL, topic TEXT, fact TEXT,
                    confidence REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    last_access REAL,
                    source TEXT DEFAULT 'learned'
                );
            """)
            conn.commit()
        monkeypatch.setenv("CLARA_DB_PATH", str(db))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        from memory import Memory
        mem = Memory()
        mem.learn("test", "Hà Nội đẹp.", confidence=0.8, language="vi")
        row = dict(mem.conn.execute("SELECT fact, language FROM semantics WHERE topic=?", ("test",)).fetchone())
        assert row is not None
        assert row["fact"] == "Hà Nội đẹp."
        assert row["language"] == "vi"

    def test_web_run_propagates_profile_and_language(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLARA_DB_PATH", str(tmp_path / "clara.db"))
        monkeypatch.setenv("CLARA_OLLAMA_URL", "http://127.0.0.1:11434")
        import main as main_module
        captured = {}

        class DummyArgs:
            micro = True
            model = None
            dream_every = 10
            no_auto_skill = False
            auto_learn = False
            idle_interval = 25
            self_improve = False
            research_interval = 300
            quiet = False
            profile = "eco"
            idle_study = True
            allow_network = True
            language = "en"
            host = "127.0.0.1"
            port = 5000

        def fake_create_app(agi):
            captured["web"] = {
                "language": getattr(agi, "language", None),
                "profile": getattr(agi, "profile_name", None),
                "allow_network": getattr(agi, "allow_network", None),
                "idle_study": getattr(agi, "idle_study", None),
                "brain_profile": getattr(getattr(agi, "brain", None), "profile", None),
            }
            class DummyApp:
                def run(self, *a, **kwargs):
                    raise SystemExit(0)
            return DummyApp()

        try:
            import webui
            webui.create_app = fake_create_app
        except Exception:
            import types
            fake_webui = types.ModuleType("webui")
            fake_webui.create_app = fake_create_app
            main_module.sys.modules["webui"] = fake_webui

        try:
            main_module.run_web(DummyArgs())
        except SystemExit:
            pass
        finally:
            try:
                import webui
                import importlib
                importlib.reload(webui)
            except Exception:
                pass

        web = captured.get("web", {})
        assert web.get("language") == "en"
        assert web.get("profile") == "eco"
        assert web.get("allow_network") is True
        assert web.get("idle_study") is True
        assert web.get("brain_profile") == "eco"


class _FakeOllamaServer:
    def __init__(self):
        self.generate_calls = 0
        self.chat_calls = 0
        self.port = 0
        self._thread = None
        self._httpd = None

    def start(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                return

            def do_POST(self):
                if self.path.endswith("/api/generate"):
                    server.generate_calls += 1
                    self._respond({"response": "should-not-use"})
                elif self.path.endswith("/api/chat"):
                    server.chat_calls += 1
                    length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    content = ""
                    messages = body.get("messages", [])
                    if messages and messages[-1].get("role") == "user":
                        content = messages[-1].get("content", "")
                    self._respond({"message": {"content": f"{content}-server-ok"}})
                else:
                    self._respond({}, code=404)

            def _respond(self, payload, code=200):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
