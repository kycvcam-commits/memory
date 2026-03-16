#!/usr/bin/env python3
"""
BlackRoad Memory 2048 — Hierarchical Memory Compression System

Like the 2048 game: when two memories at the same tier combine,
they merge into one compressed memory at the next tier.

11 Tiers:
  Tier 0  (2)    → Raw entries, most recent, highest detail
  Tier 1  (4)    → 2 raw entries compressed into 1
  Tier 2  (8)    → 2 tier-1 entries compressed into 1
  Tier 3  (16)   → Short-term patterns emerging
  Tier 4  (32)   → Working memory — recent context
  Tier 5  (64)   → Medium-term — project-level knowledge
  Tier 6  (128)  → Established patterns and solutions
  Tier 7  (256)  → Long-term institutional knowledge
  Tier 8  (512)  → Core principles and architectures
  Tier 9  (1024) → Foundational truths
  Tier 10 (2048) → Permanent memory — never compressed further

Each tier holds MAX_PER_TIER entries. When a tier reaches capacity,
the two oldest entries merge (compress) into one entry at the next tier.

Storage: SQLite with FTS5 for search across all tiers.
Compression: Extractive summarization (local, no API needed).
"""

import sqlite3
import json
import hashlib
import time
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional

DB_PATH = os.environ.get("MEMORY_2048_DB", os.path.expanduser("~/.blackroad/memory-2048.db"))

# Tier definitions
TIERS = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
TIER_NAMES = [
    "instant",       # 2    — raw entries
    "flash",         # 4    — just happened
    "recent",        # 8    — this session
    "short-term",    # 16   — last few sessions
    "working",       # 32   — active context
    "project",       # 64   — project-level
    "established",   # 128  — proven patterns
    "institutional", # 256  — org knowledge
    "core",          # 512  — architectural truths
    "foundational",  # 1024 — first principles
    "permanent",     # 2048 — never forgotten
]
MAX_PER_TIER = 64  # When a tier hits this, oldest pair merges up


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    tier INTEGER NOT NULL DEFAULT 0,
    tier_name TEXT NOT NULL DEFAULT 'instant',
    tier_size INTEGER NOT NULL DEFAULT 2,
    content TEXT NOT NULL,
    summary TEXT,
    source_ids TEXT DEFAULT '[]',
    compression_count INTEGER DEFAULT 1,
    category TEXT DEFAULT 'general',
    tags TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    merged_at REAL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tier_stats (
    tier INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    size INTEGER NOT NULL,
    count INTEGER DEFAULT 0,
    total_compressions INTEGER DEFAULT 0,
    last_merge REAL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content, summary, category, tags,
    content='memories', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memory_fts(rowid, content, summary, category, tags)
    VALUES (new.rowid, new.content, new.summary, new.category, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, content, summary, category, tags)
    VALUES ('delete', old.rowid, old.content, old.summary, old.category, old.tags);
END;
"""


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Initialize the database and tier stats."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    for stmt in SCHEMA.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Table/trigger already exists

    # Initialize tier stats
    for i, (size, name) in enumerate(zip(TIERS, TIER_NAMES)):
        conn.execute(
            "INSERT OR IGNORE INTO tier_stats (tier, name, size, count) VALUES (?, ?, ?, 0)",
            (i, name, size),
        )
    conn.commit()
    return conn


def memory_hash(content: str, tier: int) -> str:
    """Create a unique hash for a memory entry."""
    return hashlib.sha256(f"{content}:{tier}:{time.time()}".encode()).hexdigest()[:16]


def compress(text1: str, text2: str, target_tier: int) -> tuple[str, str]:
    """Compress two memory entries into one.
    Returns (compressed_content, summary).

    Uses extractive compression — keeps the most important sentences
    and merges them. No LLM needed.
    """
    # Split both texts into sentences
    sentences1 = _split_sentences(text1)
    sentences2 = _split_sentences(text2)
    all_sentences = sentences1 + sentences2

    if not all_sentences:
        return (text1 + "\n" + text2, text1[:100])

    # Score each sentence by information density
    scored = []
    for s in all_sentences:
        score = _sentence_score(s)
        scored.append((score, s))

    # Sort by score (highest first)
    scored.sort(key=lambda x: -x[0])

    # Keep top sentences — fewer as tier increases (more compression)
    # Tier 0-2: keep 75%, Tier 3-5: keep 50%, Tier 6-8: keep 33%, Tier 9-10: keep 25%
    if target_tier <= 2:
        keep_ratio = 0.75
    elif target_tier <= 5:
        keep_ratio = 0.50
    elif target_tier <= 8:
        keep_ratio = 0.33
    else:
        keep_ratio = 0.25

    keep_count = max(1, int(len(scored) * keep_ratio))
    kept = scored[:keep_count]

    # Rebuild in original order
    kept_set = {s for _, s in kept}
    result = [s for s in all_sentences if s in kept_set]

    compressed = " ".join(result)
    summary = result[0][:200] if result else compressed[:200]

    return (compressed, summary)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Simple sentence splitter
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 5]


def _sentence_score(sentence: str) -> float:
    """Score a sentence by information density.
    Higher = more important to keep.
    """
    score = 0.0

    # Length bonus (longer = more info, up to a point)
    words = sentence.split()
    score += min(len(words) / 20.0, 1.0)

    # Technical terms bonus
    tech_terms = [
        "deploy", "agent", "worker", "api", "database", "node",
        "security", "fix", "build", "error", "config", "server",
        "model", "pipeline", "cron", "backup", "migrate", "auth",
        "pi", "ollama", "nats", "cloudflare", "tunnel", "docker",
        "blackroad", "lucidia", "cecilia", "octavia", "alice", "aria",
    ]
    tech_count = sum(1 for w in words if w.lower() in tech_terms)
    score += tech_count * 0.3

    # Numbers/metrics bonus (concrete data is valuable)
    num_count = len(re.findall(r'\d+', sentence))
    score += num_count * 0.2

    # Action verbs bonus
    actions = ["created", "deployed", "fixed", "built", "added", "removed",
               "updated", "migrated", "configured", "installed", "pushed"]
    action_count = sum(1 for w in words if w.lower() in actions)
    score += action_count * 0.4

    # Code/path indicators bonus
    if any(c in sentence for c in ['/', ':', '.sh', '.py', '.js', '.ts', 'http']):
        score += 0.3

    return score


class Memory2048:
    """The 2048 memory compression engine."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = init_db(db_path)

    def store(self, content: str, category: str = "general", tags: list[str] = None) -> str:
        """Store a new memory at tier 0 (instant).
        Returns the memory ID.
        """
        mem_id = f"mem-{memory_hash(content, 0)}"
        now = time.time()

        self.conn.execute(
            """INSERT INTO memories
               (id, tier, tier_name, tier_size, content, summary, source_ids,
                compression_count, category, tags, created_at, hash)
               VALUES (?, 0, 'instant', 2, ?, ?, '[]', 1, ?, ?, ?, ?)""",
            (mem_id, content, content[:200], category,
             json.dumps(tags or []), now, memory_hash(content, 0)),
        )

        # Update tier count
        self.conn.execute(
            "UPDATE tier_stats SET count = count + 1 WHERE tier = 0"
        )
        self.conn.commit()

        # Check if tier 0 needs compression
        self._maybe_compress(0)

        return mem_id

    def _maybe_compress(self, tier: int):
        """Check if a tier needs compression. If so, merge oldest 2 entries up."""
        if tier >= len(TIERS) - 1:
            return  # Tier 10 (2048) is permanent, never compresses

        count = self.conn.execute(
            "SELECT COUNT(*) as c FROM memories WHERE tier = ?", (tier,)
        ).fetchone()["c"]

        if count < MAX_PER_TIER:
            return

        # Get the two oldest entries at this tier
        oldest = self.conn.execute(
            "SELECT * FROM memories WHERE tier = ? ORDER BY created_at ASC LIMIT 2",
            (tier,),
        ).fetchall()

        if len(oldest) < 2:
            return

        entry1, entry2 = oldest[0], oldest[1]
        next_tier = tier + 1

        # Compress
        compressed_content, summary = compress(
            entry1["content"], entry2["content"], next_tier
        )

        # Create merged entry at next tier
        source_ids = json.loads(entry1["source_ids"]) + json.loads(entry2["source_ids"])
        source_ids.extend([entry1["id"], entry2["id"]])

        # Merge tags
        tags1 = set(json.loads(entry1["tags"]))
        tags2 = set(json.loads(entry2["tags"]))
        merged_tags = list(tags1 | tags2)

        # Pick best category
        category = entry1["category"] if entry1["compression_count"] >= entry2["compression_count"] else entry2["category"]

        new_id = f"mem-{memory_hash(compressed_content, next_tier)}"
        now = time.time()
        total_compressions = entry1["compression_count"] + entry2["compression_count"]

        self.conn.execute(
            """INSERT INTO memories
               (id, tier, tier_name, tier_size, content, summary, source_ids,
                compression_count, category, tags, created_at, merged_at, hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, next_tier, TIER_NAMES[next_tier], TIERS[next_tier],
             compressed_content, summary, json.dumps(source_ids[-20:]),  # Keep last 20 source IDs
             total_compressions, category, json.dumps(merged_tags),
             min(entry1["created_at"], entry2["created_at"]),  # Keep oldest timestamp
             now, memory_hash(compressed_content, next_tier)),
        )

        # Delete the two source entries
        self.conn.execute("DELETE FROM memories WHERE id = ?", (entry1["id"],))
        self.conn.execute("DELETE FROM memories WHERE id = ?", (entry2["id"],))

        # Update tier stats
        self.conn.execute("UPDATE tier_stats SET count = count - 2 WHERE tier = ?", (tier,))
        self.conn.execute(
            "UPDATE tier_stats SET count = count + 1, total_compressions = total_compressions + 1, last_merge = ? WHERE tier = ?",
            (now, next_tier),
        )
        self.conn.commit()

        # Recursively check if next tier also needs compression
        self._maybe_compress(next_tier)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Search across all tiers using FTS5."""
        results = []
        try:
            rows = self.conn.execute(
                """SELECT m.*, rank FROM memory_fts f
                   JOIN memories m ON m.rowid = f.rowid
                   WHERE memory_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
            results = [dict(r) for r in rows]
        except Exception:
            # Fallback to LIKE search
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY tier ASC, created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            results = [dict(r) for r in rows]
        return results

    def get_tier(self, tier: int, limit: int = 50) -> list[dict]:
        """Get all memories at a specific tier."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE tier = ? ORDER BY created_at DESC LIMIT ?",
            (tier, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        """Get compression stats across all tiers."""
        tier_data = []
        total_memories = 0
        total_compressions = 0

        for row in self.conn.execute("SELECT * FROM tier_stats ORDER BY tier").fetchall():
            tier_data.append({
                "tier": row["tier"],
                "name": row["name"],
                "size": row["size"],
                "count": row["count"],
                "compressions": row["total_compressions"],
            })
            total_memories += row["count"]
            total_compressions += row["total_compressions"]

        # Calculate compression ratio
        original_count = total_memories + total_compressions * 2
        ratio = original_count / max(1, total_memories)

        return {
            "total_memories": total_memories,
            "total_compressions": total_compressions,
            "compression_ratio": round(ratio, 2),
            "original_entries": original_count,
            "space_saved_pct": round((1 - 1 / ratio) * 100, 1) if ratio > 1 else 0,
            "tiers": tier_data,
            "db_size_kb": os.path.getsize(self.db_path) // 1024 if os.path.exists(self.db_path) else 0,
        }

    def recall(self, n: int = 10) -> list[dict]:
        """Recall the most important memories (highest tier first, then most recent)."""
        rows = self.conn.execute(
            "SELECT * FROM memories ORDER BY tier DESC, created_at DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]

    def import_journal(self, journal_db: str = None):
        """Import existing journal entries as tier-0 memories."""
        journal_db = journal_db or os.path.expanduser("~/.blackroad/memory-journal.db")
        if not os.path.exists(journal_db):
            return 0

        jconn = sqlite3.connect(journal_db)
        jconn.row_factory = sqlite3.Row
        rows = jconn.execute("SELECT * FROM journal ORDER BY timestamp ASC").fetchall()

        count = 0
        for row in rows:
            content = f"[{row['action']}] {row['entity']}: {row['details']}"
            # Check if already imported
            exists = self.conn.execute(
                "SELECT 1 FROM memories WHERE content = ? LIMIT 1", (content,)
            ).fetchone()
            if not exists:
                self.store(content, category=row["action"], tags=[row["entity"]])
                count += 1

        jconn.close()
        return count

    def import_tils(self, tils_db: str = None):
        """Import existing TILs as tier-0 memories."""
        tils_db = tils_db or os.path.expanduser("~/.blackroad/memory-tils.db")
        if not os.path.exists(tils_db):
            return 0

        tconn = sqlite3.connect(tils_db)
        tconn.row_factory = sqlite3.Row
        rows = tconn.execute("SELECT * FROM tils ORDER BY created_at ASC").fetchall()

        count = 0
        for row in rows:
            content = f"[TIL:{row['category']}] {row['learning']}"
            exists = self.conn.execute(
                "SELECT 1 FROM memories WHERE content = ? LIMIT 1", (content,)
            ).fetchone()
            if not exists:
                self.store(content, category="til", tags=[row["category"]])
                count += 1

        tconn.close()
        return count

    def import_codex(self, codex_db: str = None):
        """Import codex solutions and patterns as higher-tier memories."""
        codex_db = codex_db or os.path.expanduser("~/.blackroad/memory-codex.db")
        if not os.path.exists(codex_db):
            return 0

        cconn = sqlite3.connect(codex_db)
        cconn.row_factory = sqlite3.Row
        count = 0

        for table in ["solutions", "patterns", "best_practices"]:
            try:
                rows = cconn.execute(f"SELECT * FROM {table}").fetchall()
            except Exception:
                continue

            for row in rows:
                name = row.get("name", row.get("pattern_name", ""))
                desc = row.get("solution", row.get("description", ""))
                content = f"[CODEX:{table}] {name}: {desc}"

                exists = self.conn.execute(
                    "SELECT 1 FROM memories WHERE content = ? LIMIT 1", (content,)
                ).fetchone()
                if not exists:
                    # Codex entries start at tier 6 (established) since they're proven knowledge
                    mem_id = f"mem-{memory_hash(content, 6)}"
                    now = time.time()
                    self.conn.execute(
                        """INSERT INTO memories
                           (id, tier, tier_name, tier_size, content, summary, source_ids,
                            compression_count, category, tags, created_at, hash)
                           VALUES (?, 6, 'established', 128, ?, ?, '[]', 1, ?, '[]', ?, ?)""",
                        (mem_id, content, content[:200], table, now, memory_hash(content, 6)),
                    )
                    self.conn.execute("UPDATE tier_stats SET count = count + 1 WHERE tier = 6")
                    count += 1

        self.conn.commit()
        cconn.close()
        return count


# ── CLI ──

def main():
    if len(sys.argv) < 2:
        print("""
╔══════════════════════════════════════════════════════════╗
║  BLACKROAD MEMORY 2048                                   ║
║  Hierarchical compression: 2→4→8→16→32→64→128→256→512→1024→2048  ║
╚══════════════════════════════════════════════════════════╝

Usage: python3 memory2048.py <command> [args]

Commands:
  store "<text>" [category]    Store a new memory (tier 0)
  search "<query>"             Search across all tiers
  recall [n]                   Recall top N memories (highest tier first)
  stats                        Show compression statistics
  tier <n>                     Show memories at tier N
  import                       Import journal + TILs + codex entries
  pyramid                      Show the memory pyramid visualization
""")
        return

    mem = Memory2048()
    cmd = sys.argv[1]

    if cmd == "store":
        text = sys.argv[2] if len(sys.argv) > 2 else input("Memory: ")
        category = sys.argv[3] if len(sys.argv) > 3 else "general"
        mid = mem.store(text, category)
        print(f"✓ Stored: {mid} (tier 0 / instant)")

    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else input("Search: ")
        results = mem.search(query)
        print(f"\n{len(results)} results for '{query}':\n")
        for r in results:
            tier_label = f"T{r['tier']}:{r['tier_name']}"
            print(f"  [{tier_label:20s}] {r['content'][:100]}")
            if r["compression_count"] > 1:
                print(f"  {'':22s} (compressed {r['compression_count']}x)")

    elif cmd == "recall":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        memories = mem.recall(n)
        print(f"\nTop {n} memories (highest tier first):\n")
        for r in memories:
            tier_label = f"T{r['tier']}:{r['tier_name']}"
            print(f"  [{tier_label:20s}] {r['content'][:120]}")

    elif cmd == "stats":
        s = mem.stats()
        print(f"""
╔══════════════════════════════════════════════════════════╗
║  MEMORY 2048 — COMPRESSION STATS                         ║
╚══════════════════════════════════════════════════════════╝

  Total memories:     {s['total_memories']:,}
  Original entries:   {s['original_entries']:,}
  Compressions:       {s['total_compressions']:,}
  Compression ratio:  {s['compression_ratio']}x
  Space saved:        {s['space_saved_pct']}%
  DB size:            {s['db_size_kb']} KB
""")
        print("  Tier  Name            Size   Count  Compressions")
        print("  ────  ──────────────  ─────  ─────  ────────────")
        for t in s["tiers"]:
            bar = "█" * min(30, t["count"]) + "░" * max(0, min(30, MAX_PER_TIER - t["count"]))
            print(f"  {t['tier']:>4}  {t['name']:14s}  {t['size']:>5}  {t['count']:>5}  {t['compressions']:>5}  {bar}")

    elif cmd == "tier":
        tier = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        memories = mem.get_tier(tier)
        name = TIER_NAMES[tier] if tier < len(TIER_NAMES) else "unknown"
        print(f"\nTier {tier} ({name}, size {TIERS[tier]}): {len(memories)} memories\n")
        for r in memories:
            print(f"  [{r['id']}] {r['content'][:120]}")
            if r["compression_count"] > 1:
                print(f"    compressed {r['compression_count']}x | sources: {r['source_ids'][:80]}")

    elif cmd == "import":
        print("Importing existing memory data...")
        j = mem.import_journal()
        print(f"  Journal: {j} entries imported")
        t = mem.import_tils()
        print(f"  TILs: {t} entries imported")
        c = mem.import_codex()
        print(f"  Codex: {c} entries imported (→ tier 6)")
        s = mem.stats()
        print(f"\n  Total: {s['total_memories']} memories, {s['total_compressions']} compressions, {s['compression_ratio']}x ratio")

    elif cmd == "pyramid":
        s = mem.stats()
        print(f"""
                    ╱╲
                   ╱2048╲     ← Permanent memory (never compressed)
                  ╱──────╲
                 ╱  1024  ╲   ← Foundational truths
                ╱──────────╲
               ╱    512     ╲  ← Core principles
              ╱──────────────╲
             ╱      256       ╲ ← Institutional knowledge
            ╱──────────────────╲
           ╱       128          ╲← Established patterns
          ╱──────────────────────╲
         ╱         64             ╲← Project-level
        ╱──────────────────────────╲
       ╱          32                ╲← Working memory
      ╱──────────────────────────────╲
     ╱           16                   ╲← Short-term
    ╱──────────────────────────────────╲
   ╱            8                       ╲← Recent
  ╱──────────────────────────────────────╲
 ╱             4                          ╲← Flash
╱──────────────────────────────────────────╲
╲              2 (instant)                 ╱← Raw entries
 ╲────────────────────────────────────────╱
""")
        print("  Tier  Name            Count  Compressions")
        for t in s["tiers"]:
            bar = "█" * t["count"] if t["count"] < 40 else "█" * 40 + f"...({t['count']})"
            print(f"  T{t['tier']:>2}   {t['name']:14s}  {t['count']:>5}  {t['compressions']:>5}  {bar}")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
