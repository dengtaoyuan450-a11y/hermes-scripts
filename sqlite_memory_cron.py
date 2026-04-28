#!/usr/bin/env python3
"""
sqlite-memory-mcp 记忆 Cron 任务
直接读写 ~/.claude/memory/memory.db，与 MCP 服务器共享同一数据库

用法:
  python sqlite_memory_cron.py consolidate "<内容>" "<实体名>"
  python sqlite_memory_cron.py search "<关键词>" [top_k]
  python sqlite_memory_cron.py status

注意: 无需 MCP 协议，直接 SQL 操作，与 sqlite-memory-mcp MCP 服务器共享同一 DB 文件
"""

import json
import sqlite3
import sys
import os
from datetime import datetime

# ── Database path（与 sqlite-memory-mcp server.py 一致） ───────────────────

DB_PATH = os.environ.get(
    "SQLITE_MEMORY_DB",
    os.path.expanduser("~/.claude/memory/memory.db"),
)


def _get_conn():
    """获取数据库连接。"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


# ── Core API ───────────────────────────────────────────────────────────

def consolidate_memory(content: str, entity_name: str = None,
                       entity_type: str = "market_event",
                       project: str = "astock") -> dict:
    """
    盘后记忆整理：创建或更新实体 + 添加 observation
    """
    now = datetime.utcnow().isoformat()
    if entity_name is None:
        entity_name = f"{project}:{datetime.now().strftime('%Y%m%d')}"

    summary = content[:80].replace("\n", " ").strip()

    with _get_conn() as conn:
        # 插入或更新实体
        cur = conn.execute("""
            INSERT INTO entities (name, entity_type, project, visibility, origin, created_at, updated_at)
            VALUES (?, ?, ?, 'private', 'local', ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                updated_at=excluded.updated_at
        """, (entity_name, entity_type, project, now, now))

        entity_id = cur.lastrowid or conn.execute(
            "SELECT id FROM entities WHERE name=?", (entity_name,)).fetchone()[0]

        # 添加 observation
        try:
            conn.execute("""
                INSERT INTO observations (entity_id, content, created_at)
                VALUES (?, ?, ?)
            """, (entity_id, content, now))
        except sqlite3.IntegrityError:
            # 同一 entity_id + content 重复添加，跳过
            pass

        conn.commit()

    return {
        "status": "consolidated",
        "entity": entity_name,
        "entity_id": entity_id,
        "content_preview": summary,
        "timestamp": now,
    }


def search_memory(query: str, top_k: int = 5, project: str = "astock") -> dict:
    """
    搜索记忆：FTS5 BM25 全文检索
    """
    from fnmatch import fnmatch

    # 简单 FTS5 query 预处理
    fts_q = " ".join(f'"{t}"' for t in query.split() if t)

    with _get_conn() as conn:
        rows = conn.execute(f"""
            SELECT e.id, e.name, e.entity_type, o.content, o.created_at,
                   bm25(memory_fts) as rank
            FROM memory_fts f
            JOIN entities e ON e.id = f.rowid
            LEFT JOIN observations o ON o.entity_id = e.id
            WHERE memory_fts MATCH ? AND (e.project = ? OR e.project IS NULL OR e.project = 'astock')
            ORDER BY rank
            LIMIT ?
        """, (fts_q, project, top_k * 3)).fetchall()

        results = []
        seen = set()
        for row in rows:
            name = row["name"]
            if name not in seen:
                seen.add(name)
                results.append({
                    "entity_id": row["id"],
                    "entity_name": name,
                    "entity_type": row["entity_type"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "rank": row["rank"],
                })
            if len(results) >= top_k:
                break

    return {
        "status": "searched",
        "query": query,
        "count": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def read_graph(project: str = "astock") -> dict:
    """读取当前知识图谱概览。"""
    with _get_conn() as conn:
        entities = conn.execute("""
            SELECT id, name, entity_type, project, updated_at
            FROM entities
            WHERE project = ? OR ? IS NULL
            ORDER BY updated_at DESC LIMIT 20
        """, (project, project)).fetchall()

        obs_count = conn.execute("""
            SELECT COUNT(*) FROM observations o
            JOIN entities e ON e.id = o.entity_id
            WHERE e.project = ? OR ? IS NULL
        """, (project, project)).fetchone()[0]

    return {
        "status": "ok",
        "total_entities": len(entities),
        "total_observations": obs_count,
        "recent_entities": [
            {"id": r["id"], "name": r["name"], "type": r["entity_type"], "updated": r["updated_at"]}
            for r in entities
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python sqlite_memory_cron.py consolidate <内容> [实体名] [类型] [项目]")
        print("  python sqlite_memory_cron.py search <关键词> [top_k]")
        print("  python sqlite_memory_cron.py status")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "consolidate":
        if len(sys.argv) < 3:
            print("错误: consolidate 需要内容参数")
            sys.exit(1)
        content = sys.argv[2]
        entity_name = sys.argv[3] if len(sys.argv) > 3 else None
        entity_type = sys.argv[4] if len(sys.argv) > 4 else "market_event"
        project = sys.argv[5] if len(sys.argv) > 5 else "astock"
        result = consolidate_memory(content, entity_name, entity_type, project)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "search":
        if len(sys.argv) < 3:
            print("错误: search 需要查询参数")
            sys.exit(1)
        query = sys.argv[2]
        top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        result = search_memory(query, top_k)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "status":
        result = read_graph()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
