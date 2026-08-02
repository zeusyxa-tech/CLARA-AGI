#!/usr/bin/env python3
"""CLARA-AGI v1.2 headless autopilot: dedup + ethics + curriculum."""
import os, sys, time, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


class SilentStdin:
    def readline(self):
        time.sleep(1)
        return "\n"

    def fileno(self):
        return 0


def main():
    sys.stdin = SilentStdin()

    import argparse
    from agent import ClarasAGI
    from autolearn import AutoLearner
    from curriculum import daily_plan, load_policy, LEVELS, is_ethical, _score_topic
    from self_improve import research
    from self_improve_loop import SelfImprovementLoop

    policy = load_policy()

    args = argparse.Namespace(
        micro=False, model="qwen2.5:1.5b", web=False, voice=False,
        dream_every=20, no_auto_skill=False,
        auto_learn=True, self_improve=True,
        research_interval=300, idle_interval=25, quiet=True,
    )

    agi = ClarasAGI(
        force_micro=args.micro,
        model=args.model,
        dream_every=args.dream_every,
        auto_skill=not args.no_auto_skill,
    )

    # seed behavior policy nếu chưa có
    for k, v in {
        "research_mode": "curriculum",
        "ethics_filter": True,
        "dedup_window_hours": "24",
        "min_usefulness": str(policy.get("min_usefulness", 0.35)),
    }.items():
        try:
            agi.mem.set_policy(k, v)
        except Exception:
            pass

    # status
    try:
        s = agi.status()
        print(f"🧠 Brain : {s['brain']['backend']} — {s['brain']['model']}", flush=True)
        print(f"💾 Memory: {s['memory']['episodes']} episodes · "
              f"{s['memory']['semantics']} facts · "
              f"procedures={s['memory']['procedures']}", flush=True)
        print(f"🎯 Goals : active={s['memory']['active_goals']} done={s['memory']['done_goals']}", flush=True)
        print(f"⏱ Age   : {s['age_hours']:.1f}h · turns={s['turns']}", flush=True)
    except Exception as e:
        print("status err:", e, flush=True)

    auto = AutoLearner(agi, interval=args.idle_interval, verbose=not args.quiet)
    auto.start()
    print("✅ Tự học nền đã bật", flush=True)

    improver_running = {"on": True}

    def research_loop():
        import random
        time.sleep(10)
        day = int(time.time() // 86400)
        while improver_running["on"]:
            try:
                plan = daily_plan(day)
                topic = plan["topic"]
                score = _score_topic(topic, policy)
                print(f"[autopilot] curriculum plan: {plan['level']} → {topic} (score={score:.2f})", flush=True)

                seen = [x["topic"] for x in agi.mem.seen_topics(limit=300)]
                if topic in seen:
                    topic = random.choice(LEVELS[day % len(LEVELS)]["topics"])
                if not is_ethical(topic, policy):
                    print(f"[autopilot] skip unethical topic: {topic}", flush=True)
                    day += 1
                    continue

                result = research(agi, topic, max_pages=1)
                agi.mem.log_research(
                    topic=topic,
                    source="curriculum",
                    result_summary=str(result)[:200],
                    usefulness=score,
                )
                agi.mem.mark_topic_done(topic)
                print(f"[autopilot] learned: {topic}", flush=True)
            except Exception as e:
                print(f"[autopilot] research err: {e}", flush=True)
            for _ in range(args.research_interval):
                if not improver_running["on"]:
                    return
                time.sleep(1)

    threading.Thread(target=research_loop, daemon=True).start()
    print("✅ Tự nghiên cứu web theo curriculum đã bật", flush=True)

    improve_loop = SelfImprovementLoop(agi, interval=360, verbose=True)
    improve_loop.start()
    print("✅ Vòng cải thiện bản thân đã bật", flush=True)

    print("[autopilot] CLARA v1.2 started. Ctrl+C / kill PID to stop.", flush=True)
    try:
        while True:
            time.sleep(60)
    except Exception:
        pass
    finally:
        improver_running["on"] = False
        auto.stop()
        try:
            improve_loop.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
