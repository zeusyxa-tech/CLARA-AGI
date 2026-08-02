"""
CLARA-AGI - Code curriculum for self-improvement.
Tự chọn chủ đề học code theo ngày: cơ bản -> trung cấp -> nâng cao.
"""
import time, random

LEVELS = [
    {
        "name": "python_basics",
        "topics": [
            "python function example safe",
            "python string processing example",
            "python data validation simple",
            "python list comprehension safe example",
            "python datetime calculation example",
        ],
    },
    {
        "name": "tooling_safety",
        "topics": [
            "python AST safety check example",
            "python sandbox code execution",
            "python file allowlist path",
            "python safe math expression parser",
        ],
    },
    {
        "name": "web_automation",
        "topics": [
            "python html text extraction example",
            "python safe web fetch example",
            "python search result parser example",
            "python url redirect decoder example",
        ],
    },
    {
        "name": "self_patching",
        "topics": [
            "python small refactor example safe",
            "python AST transformation example",
            "python module reload safe",
            "python backup diff example",
        ],
    },
]


def pick_topic_for_day(day: int):
    idx = day % len(LEVELS)
    topics = LEVELS[idx]["topics"]
    return LEVELS[idx]["name"], random.choice(topics)


def daily_plan(day: int = 0):
    if not day:
        day = int(time.time() // 86400)
    lvl, topic = pick_topic_for_day(day)
    return {
        "day": day,
        "level": lvl,
        "topic": topic,
        "action": f"research '{topic}' then propose skill or patch",
    }
