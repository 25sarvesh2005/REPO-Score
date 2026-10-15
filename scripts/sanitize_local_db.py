"""
Database Sanitization Script for RepoScore Local Development.
Prunes mock/synthetic test repositories (e.g. acme/*, evil/*) and stranded test evaluations,
preserving legitimate evaluated user repositories.
"""

import sqlite3
from pathlib import Path


def sanitize_database(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        print(f"Database {db_path} does not exist.")
        return {}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")

    # Find mock repository IDs
    cur.execute("SELECT id, owner, name FROM repositories WHERE owner IN ('acme', 'evil')")
    mock_repos = cur.fetchall()
    print(
        f"Found {len(mock_repos)} mock repositories to prune: {[r[1] + '/' + r[2] for r in mock_repos]}"
    )

    if not mock_repos:
        conn.close()
        return {}

    repo_ids = [r[0] for r in mock_repos]
    placeholders = ",".join("?" for _ in repo_ids)

    # Find affected evaluation IDs
    cur.execute(f"SELECT id FROM evaluations WHERE repository_id IN ({placeholders})", repo_ids)
    eval_ids = [r[0] for r in cur.fetchall()]
    eval_placeholders = ",".join("?" for _ in eval_ids) if eval_ids else "''"

    counts: dict[str, int] = {}

    if eval_ids:
        # Delete score dimensions
        cur.execute(f"SELECT id FROM scores WHERE evaluation_id IN ({eval_placeholders})", eval_ids)
        score_ids = [r[0] for r in cur.fetchall()]
        if score_ids:
            score_placeholders = ",".join("?" for _ in score_ids)
            cur.execute(
                f"DELETE FROM score_dimensions WHERE score_id IN ({score_placeholders})", score_ids
            )
            counts["score_dimensions"] = cur.rowcount

        # Delete scores
        cur.execute(f"DELETE FROM scores WHERE evaluation_id IN ({eval_placeholders})", eval_ids)
        counts["scores"] = cur.rowcount

        # Delete AI analysis
        cur.execute(
            f"DELETE FROM ai_analyses WHERE evaluation_id IN ({eval_placeholders})", eval_ids
        )
        counts["ai_analyses"] = cur.rowcount

        # Delete evidence
        cur.execute(f"DELETE FROM evidence WHERE evaluation_id IN ({eval_placeholders})", eval_ids)
        counts["evidence"] = cur.rowcount

        # Delete runtime observations
        cur.execute(
            f"DELETE FROM runtime_observations WHERE evaluation_id IN ({eval_placeholders})",
            eval_ids,
        )
        counts["runtime_observations"] = cur.rowcount

        # Delete evaluation steps
        cur.execute(
            f"DELETE FROM evaluation_steps WHERE evaluation_id IN ({eval_placeholders})", eval_ids
        )
        counts["evaluation_steps"] = cur.rowcount

        # Delete evaluations
        cur.execute(f"DELETE FROM evaluations WHERE id IN ({eval_placeholders})", eval_ids)
        counts["evaluations"] = cur.rowcount

    # Delete snapshots
    cur.execute(
        f"DELETE FROM repository_snapshots WHERE repository_id IN ({placeholders})", repo_ids
    )
    counts["snapshots"] = cur.rowcount

    # Delete repositories
    cur.execute(f"DELETE FROM repositories WHERE id IN ({placeholders})", repo_ids)
    counts["repositories"] = cur.rowcount

    conn.commit()

    # Reclaim space
    cur.execute("VACUUM;")
    conn.close()

    print("Database sanitization complete:")
    for table, count in counts.items():
        print(f"  - {table}: {count} records removed")

    return counts


if __name__ == "__main__":
    db_file = Path("reposcore_local.db")
    sanitize_database(db_file)
