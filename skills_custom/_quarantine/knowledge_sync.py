#!/usr/bin/env python3
"""
CLARA-AGI Skill: knowledge_sync
Sync knowledge across local/markdown/notion-like storages.
"""
import pathlib, json, re


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: sync:<subcmd>|<args>\n"
                "  export:<path>     export semantic memory to markdown\n"
                "  import:<path>     import facts from markdown/newline-delimited\n"
                "  obsidian:<path>   scan obsidian vault for notes\n"
                "  index             rebuild local knowledge index")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    try:
        if sub.startswith("export"):
            p = pathlib.Path(arg.strip() or "workspace/knowledge_export.md")
            rows = agi.mem.conn.execute("SELECT topic, fact, confidence FROM semantics ORDER BY last_access DESC LIMIT 200").fetchall()
            lines = ["# CLARA Knowledge Export", ""]
            for r in rows:
                lines.append(f"- [{r['topic']}] {r['fact']} (conf={r['confidence']:.2f})")
            p.write_text("\n".join(lines), encoding="utf-8")
            return f"✅ Exported {len(lines)-2} facts to {p}"
        if sub.startswith("import"):
            p = pathlib.Path(arg.strip())
            if not p.exists():
                return f"❌ missing {p}"
            txt = p.read_text(encoding="utf-8", errors="replace")
            count = 0
            for line in txt.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                topic = line.split("]", 1)[0].replace("[", "").strip() if "]" in line else "imported"
                fact = line.split("]", 1)[1].strip() if "]" in line else line
                if 5 < len(fact) < 500:
                    agi.mem.learn(topic, fact, confidence=0.6, source="import")
                    count += 1
            return f"✅ Imported {count} facts"
        if sub.startswith("obsidian"):
            vault = pathlib.Path(arg.strip() or ".")
            if not vault.exists():
                return f"❌ missing {vault}"
            files = list(vault.rglob("*.md"))[:50]
            count = 0
            for fp in files:
                txt = fp.read_text(encoding="utf-8", errors="replace")
                for line in txt.splitlines():
                    if line.startswith("- "):
                        fact = line[2:].strip()
                        if 8 < len(fact) < 300:
                            agi.mem.learn(fp.stem, fact, confidence=0.5, source="obsidian")
                            count += 1
            return f"✅ Indexed {count} bullets from {len(files)} obsidian files"
        if sub == "index":
            agi.mem.remember_episode("knowledge_index", "Rebuilt knowledge index", importance=0.3, emotion=0.0)
            return "✅ Knowledge index rebuild queued."
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
