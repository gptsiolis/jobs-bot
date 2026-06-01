"""One-time import of seen_jobs.json into Supabase as archived jobs."""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from storage import SupabaseJobStore, migrated_seen_record

DEFAULT_BATCH_SIZE = 500


def load_seen_ids(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return sorted(data.keys())
    if isinstance(data, list):
        return sorted(str(item) for item in data)
    raise ValueError(f"Unsupported seen_jobs format in {path}")


def main():
    load_dotenv(os.path.join(ROOT, ".env"))

    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="seen_jobs.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    if not os.path.exists(args.path):
        raise SystemExit(f"{args.path} does not exist")

    seen_ids = load_seen_ids(args.path)
    records = [migrated_seen_record(job_id) for job_id in seen_ids]
    if args.dry_run:
        print(f"Would archive {len(records)} legacy seen jobs.")
        return

    store = SupabaseJobStore()
    total_written = 0
    total_new = 0
    for start in range(0, len(records), args.batch_size):
        batch = records[start:start + args.batch_size]
        result = store.upsert_records(batch)
        total_written += result["total_written"]
        total_new += result["total_new"]
        print(f"Archived {total_written}/{len(records)} legacy seen jobs...")
    print(
        f"Archived {total_written} legacy seen jobs "
        f"({total_new} newly inserted)."
    )


if __name__ == "__main__":
    main()
