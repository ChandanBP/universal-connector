"""
Trust Decay Script — run as a scheduled job (daily cron recommended).

Algorithm:
  new_weight = weight * e^(-decay_rate * days_since_last_reinforcement)

Thresholds:
  < 0.15  → status = 'dormant'   (stops appearing in traversal)
  < 0.40  → status = 'decaying'
  >= 0.40 → status = 'active'

Cleanup:
  Edges dormant for > 90 days are deleted (hard forgetting).

Run:
  python -m scripts.decay_trust
  python -m scripts.decay_trust --dry-run     # preview without writing
  python -m scripts.decay_trust --domain electronics
"""

import argparse
import math
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

try:
    import psycopg2
except ImportError:
    raise ImportError("Run: pip install psycopg2-binary")


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url)


def run_decay(dry_run: bool = False, domain: str | None = None):
    conn = get_conn()
    cur  = conn.cursor()
    now  = datetime.now(timezone.utc)

    domain_filter = "AND domain = %s" if domain else ""
    params_base   = (domain,) if domain else ()

    # ── Fetch edges that need decay ───────────────────────────────────────────
    cur.execute(f"""
        SELECT id, domain, from_user_id, to_user_id,
               weight, decay_rate, last_reinforced_at, status
        FROM trust_edges
        WHERE status IN ('active', 'decaying')
          AND last_reinforced_at < NOW() - INTERVAL '7 days'
          {domain_filter}
        ORDER BY last_reinforced_at ASC
    """, params_base)

    rows = cur.fetchall()
    print(f"[decay] {len(rows)} edges to process"
          + (f" (domain={domain})" if domain else "")
          + (" [DRY RUN]" if dry_run else ""))

    updated  = 0
    dormant  = 0
    deleted  = 0

    for row in rows:
        edge_id, edge_domain, from_id, to_id, weight, decay_rate, last_reinforced, status = row

        if last_reinforced is None:
            continue

        # Make timezone-aware if naive
        if last_reinforced.tzinfo is None:
            last_reinforced = last_reinforced.replace(tzinfo=timezone.utc)

        days_inactive = (now - last_reinforced).days
        if days_inactive < 7:
            continue

        # Delete edges dormant > 90 days (hard forgetting)
        if status == 'dormant' and days_inactive > 90:
            if not dry_run:
                cur.execute("DELETE FROM trust_edges WHERE id = %s", (edge_id,))
            deleted += 1
            print(f"  [DELETE] {edge_domain} {from_id[:8]}→{to_id[:8]} "
                  f"dormant {days_inactive}d (weight={weight:.3f})")
            continue

        # Apply exponential decay: w * e^(-λ * days)
        new_weight = weight * math.exp(-decay_rate * days_inactive)
        new_weight = round(max(0.0, min(1.0, new_weight)), 4)

        new_status = (
            'dormant'  if new_weight < 0.15 else
            'decaying' if new_weight < 0.40 else
            'active'
        )

        if new_weight == weight:
            continue  # no meaningful change

        if dry_run:
            print(f"  [WOULD] {edge_domain} {from_id[:8]}→{to_id[:8]} "
                  f"{weight:.3f}→{new_weight:.3f} ({days_inactive}d) status={new_status}")
        else:
            cur.execute("""
                UPDATE trust_edges
                SET weight     = %s,
                    status     = %s,
                    updated_at = %s
                WHERE id = %s
            """, (new_weight, new_status, now.isoformat(), edge_id))

        updated += 1
        if new_status == 'dormant':
            dormant += 1

    if not dry_run:
        conn.commit()

    cur.close()
    conn.close()

    print(f"[decay] Done — updated={updated} dormant={dormant} deleted={deleted}"
          + (" [DRY RUN — no changes written]" if dry_run else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply trust decay to all edges")
    parser.add_argument("--dry-run",  action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--domain",   default=None,        help="Limit to one domain")
    args = parser.parse_args()

    run_decay(dry_run=args.dry_run, domain=args.domain)
