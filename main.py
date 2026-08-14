#!/usr/bin/env python3
"""
CLARA-AGI v1.1 — CLI launcher.
Chạy: python3 main.py [--micro] [--model <name>] [--web] [--voice] [--auto-learn]
"""
import argparse, sys, os, json, time, random, threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

WELCOME = """
╔═══════════════════════════════════════════════════════════════╗
║   🧬  CLARA-AGI  v1.3  —  Tác nhân tự chủ kiểu AGI          ║
║     local-first · chạy CPU · tự học · tự phản tỉnh          ║
╚═══════════════════════════════════════════════════════════════╝
"""


def print_status(agi):
    s = agi.status()
    print(f"   🧠 Brain     : {s['brain']['backend']} — {s['brain']['model']}")
    print(f"   💾 Memory    : {s['memory']['episodes']} episodes · "
          f"{s['memory']['semantics']} facts · "
          f"{s['memory']['procedures']} procedures (auto: {s['memory']['auto_procedures']})")
    print(f"   🎯 Goals     : {s['memory']['active_goals']} active / {s['memory']['done_goals']} done")
    print(f"   💭 Dreams    : {s['memory']['dreams']}")
    print(f"   ⏱️ Age       : {s['age_hours']}h · {s['turns']} turns")
    if s["brain"]["backend"] == "micro":
        print()
        print("💡 Chưa phát hiện Ollama. Tôi đang chạy 'micro brain' — đủ thể hiện kiến")
        print("   trúc AGI nhưng trí tuệ hạn chế. Cách nâng cấp (chỉ làm 1 lần):")
        print("     Windows: tải https://ollama.com/download, cài, mở app, rồi:")
        print("              ollama pull qwen2.5:1.5b")
        print("     Linux:   curl -fsSL https://ollama.com/install.sh | sh")
        print("              (sau đó chạy 'ollama serve' trong terminal khác)")
        print("              ollama pull qwen2.5:1.5b")
        print("   Model cho máy rất yếu (4GB RAM): qwen2.5:0.5b (~350MB)")
    print("-" * 63)
    print(" Lệnh: commands · status · dream · autolearn on/off · goal X · export · quit")
    print()


def run_cli(args):
    from agent import ClarasAGI
    agi = ClarasAGI(force_micro=args.micro, model=args.model,
                    dream_every=args.dream_every, auto_skill=not args.no_auto_skill)
    print(WELCOME)
    print_status(agi)

    # Auto-learn (tự học khi treo máy)
    from autolearn import AutoLearner
    auto = AutoLearner(agi, interval=args.idle_interval, verbose=True)
    if args.auto_learn:
        auto.start()
        print(f"💤 Chế độ TỰ HỌC KHI RẢNH đã BẬT (mỗi {args.idle_interval}s, dùng CPU thấp).")
        print("   Gõ 'autolearn off' để tắt, 'autolearn status' để xem tiến độ.")
        print()

    # Self-improve (tự lên mạng học code, đề xuất skill mới)
    improver = None
    if args.self_improve:
        from self_improve import improve, list_pending, approve_skill, reject_skill, load_custom_skills, research
        loaded = load_custom_skills(agi)
        if loaded:
            print(f"🛠️ Đã nạp {len(loaded)} skill tự tạo trước đó: {', '.join(loaded)}")
        # bật thread nghiên cứu định kỳ
        import threading, random
        def _research_loop():
            time.sleep(15)
            topics = [
                "python useful utility function example",
                "cách tính chiết khấu phần trăm trong Python",
                "python convert between units",
                "simple data validation python function",
                "cách đếm số ngày giữa hai ngày trong Python",
                "cách tạo mật khẩu ngẫu nhiên an toàn Python",
                "python text processing tips",
                "cách tính chỉ số BMI Python",
            ]
            while True:
                if not getattr(improver_running, "on", True): break
                try:
                    topic = random.choice(topics)
                    print(f"\r🌐 [tự nâng cấp] đang nghiên cứu: {topic}")
                    research(agi, topic, max_pages=1)
                    print(f"\r🌐 [tự nâng cấp] đã học xong '{topic}'")
                except Exception as e:
                    print(f"\r🌐 [tự nâng cấp] lỗi: {e}")
                # ngủ theo chu kỳ research-interval
                for _ in range(args.research_interval):
                    if not getattr(improver_running, "on", True): return
                    time.sleep(1)
        class ImproverRunning: on = True
        improver_running = ImproverRunning()
        t = threading.Thread(target=_research_loop, daemon=True); t.start()
        print(f"🌐 Chế độ TỰ NÂNG CẤP đã BẬT (mỗi {args.research_interval}s tìm trên web học thêm).")
        print()

    if agi.first_run:
        print("🎉 Có vẻ đây là lần đầu chúng ta gặp nhau! Hãy bắt đầu bằng cách cho tôi")
        print("   biết tên bạn, hoặc cứ nói bất cứ điều gì bạn muốn.\n")

    while True:
        try:
            u = input("Bạn > ").strip()
        except (EOFError, KeyboardInterrupt):
            auto.stop()
            print("\n👋 Tạm biệt! Tôi giữ hết trí nhớ cho lần gặp sau.")
            break
        if not u:
            continue
        low = u.lower()
        if low in ("quit","exit","bye","thoát","bye bye"):
            auto.stop()
            print("👋 Tạm biệt! Hẹn gặp lại — tôi sẽ giữ mọi thứ đã học.")
            break
        # lệnh điều khiển tự học
        if low.startswith("autolearn"):
            rest = low[len("autolearn"):].strip()
            if rest in ("on","bật","start"):
                if auto.start():
                    print(f"✅ Đã BẬT tự học nền (mỗi {args.idle_interval}s).")
                else:
                    print("ℹ️ Tự học đang chạy rồi.")
            elif rest in ("off","tắt","stop"):
                auto.stop()
                print("🛑 Đã tắt tự học nền.")
            elif rest in ("status","stat","trạng thái"):
                print(json.dumps(auto.status(), ensure_ascii=False, indent=2))
            else:
                print("Sử dụng: autolearn on | off | status")
            print()
            continue
        # lệnh self-improve
        if low.startswith(("learn ", "nghiên cứu ", "research ", "học ")):
            from self_improve import improve
            topic = re.sub(r"^(learn|nghiên cứu|research|học)\s*[:\-]?\s*", "", low).strip()
            print("🔎 Đang tìm hiểu và đề xuất skill mới...")
            out = improve(agi, topic)
            print(out)
            print()
            continue
        if low.startswith("search ") or low.startswith("tìm "):
            from web_tools import web_search
            q = re.sub(r"^(search|tìm)\s*[:\-]?\s*", "", low).strip()
            print("🔎 Tìm kiếm...")
            res = web_search(q, max_results=5)
            for i, r in enumerate(res, 1):
                if "error" in r:
                    print(r["error"]); break
                print(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}\n")
            print()
            continue
        if low.startswith("pending"):
            from self_improve import list_pending
            items = list_pending()
            if not items:
                print("📭 Không có skill nào đang chờ duyệt.")
            else:
                print(f"📋 Skill chờ duyệt ({len(items)}):")
                for it in items:
                    print(f"  • {it['file']}  ({it['size']}B)")
                print("Dùng 'approve <tên>' để kích hoạt, 'reject <tên>' để xóa.")
            print()
            continue
        if low.startswith("approve"):
            from self_improve import approve_skill
            name = low[len("approve"):].strip()
            print(approve_skill(name)); print(); continue
        if low.startswith("reject"):
            from self_improve import reject_skill
            name = low[len("reject"):].strip()
            print(reject_skill(name)); print(); continue
        if low.startswith("skills"):
            from self_improve import list_active
            items = list_active()
            procs = agi.mem.list_procedures()
            print(f"🛠️ Skill đã kích hoạt ({len(items)}):")
            for it in items: print(f"  • {it['file']}")
            print(f"\n📚 Thủ tục nội tại ({len(procs)}):")
            for p in procs[:20]: print(f"  • {p['name']} (wr={p['success_rate']:.2f})")
            print()
            continue
        # lệnh CLI khác xử lý đặc biệt (quit đã bắt, commands/status/dream/goal/forget/export do agent xử lý)
        try:
            out = agi.chat(u)
        except Exception as e:
            out = f"❌ Lỗi nội bộ: {e}"
        print("CLARA>", out)

        # Thỉnh thoảng hỏi bạn điều tò mò (do autolearn nghĩ ra khi rảnh)
        pending = agi.mem.recall_episodes(kind="pending_question", limit=1, recent_only=True)
        if pending and random.random() < 0.3:
            q = pending[0]["content"]
            print(f"🤔 Nhân tiện, {q}")
            agi.mem.conn.execute("DELETE FROM episodes WHERE id=?", (pending[0]["id"],))
            agi.mem.conn.commit()
        print()


def run_web(args):
    try:
        from webui import create_app
    except ImportError as e:
        print(f"❌ Không thể nạp webui: {e}")
        print("   Cài thêm flask: pip install flask")
        sys.exit(1)
    from agent import ClarasAGI
    from autolearn import AutoLearner
    agi = ClarasAGI(force_micro=args.micro, model=args.model,
                    dream_every=args.dream_every, auto_skill=not args.no_auto_skill)
    auto = None
    if args.auto_learn:
        auto = AutoLearner(agi, interval=args.idle_interval, verbose=False)
        auto.start()
        print(f"💤 Tự học nền BẬT (mỗi {args.idle_interval}s).")
    app = create_app(agi)
    host = args.host or "127.0.0.1"
    port = args.port or 5000
    print(WELCOME)
    print(f"🌐 Web UI đang chạy tại  http://{host}:{port}")
    print("   Mở trình duyệt để nói chuyện với CLARA. Nhấn Ctrl+C để dừng.")
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        if auto: auto.stop()
        print("\n👋 Đã dừng.")


def run_voice(args):
    try:
        from voice import VoiceCLARA
    except ImportError as e:
        print(f"❌ Không thể nạp voice module: {e}")
        print("   Cần: pip install SpeechRecognition pyttsx3 pyaudio")
        sys.exit(1)
    from agent import ClarasAGI
    agi = ClarasAGI(force_micro=args.micro, model=args.model)
    v = VoiceCLARA(agi)
    print(WELCOME)
    print("🎙️ Chế độ giọng nói đã sẵn sàng. Nhấn Enter để nói, hoặc Ctrl+C để dừng.")
    try:
        v.loop()
    except KeyboardInterrupt:
        print("\n👋 Tạm biệt!")


def main():
    ap = argparse.ArgumentParser(description="CLARA-AGI v1.1")
    ap.add_argument("--micro", action="store_true", help="Bắt buộc dùng micro brain (không Ollama)")
    ap.add_argument("--model", type=str, default=None, help="Model Ollama (vd qwen2.5:0.5b)")
    ap.add_argument("--web", action="store_true", help="Mở giao diện web")
    ap.add_argument("--voice", action="store_true", help="Chế độ giọng nói")
    ap.add_argument("--host", type=str, default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--dream-every", type=int, default=10,
                    help="Số lượt nói rồi tôi tự 'ngủ mơ' tổng hợp (0=tắt)")
    ap.add_argument("--no-auto-skill", action="store_true", help="Tắt tự tạo skill mới")
    ap.add_argument("--auto-learn", action="store_true", default=True,
                    help="BẬT chế độ tự học khi rảnh (mặc định bật; dùng --no-auto-learn để tắt)")
    ap.add_argument("--no-auto-learn", action="store_false", dest="auto_learn",
                    help="Tắt tự học nền khi khởi động")
    ap.add_argument("--self-improve", action="store_true", default=True,
                    help="BẬT chế độ TỰ NÂNG CẤP (mặc định bật; dùng --no-self-improve để tắt)")
    ap.add_argument("--no-self-improve", action="store_false", dest="self_improve",
                    help="Tắt tự nghiên cứu web khi khởi động")
    ap.add_argument("--research-interval", type=int, default=300,
                    help="Số giây giữa mỗi lần tự nghiên cứu web (mặc định 300 = 5 phút). Chỉ dùng với --self-improve")
    ap.add_argument("--idle-interval", type=int, default=25,
                    help="Số giây giữa mỗi bước tự học (mặc định 25). Tăng lên nếu thấy CPU nóng.")
    ap.add_argument("--quiet", action="store_true", help="Bớt log tự học")
    args = ap.parse_args()

    if args.web:
        run_web(args)
    elif args.voice:
        run_voice(args)
    else:
        run_cli(args)


if __name__ == "__main__":
    main()
