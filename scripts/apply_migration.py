"""Apply a SQL migration file to the Supabase Postgres database."""

import argparse
import os
import sys

from dotenv import load_dotenv


ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()

    load_dotenv(os.path.join(ROOT, ".env"))
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise SystemExit("SUPABASE_DATABASE_URL is required.")

    import psycopg

    with open(args.path, "r", encoding="utf-8") as f:
        sql = f.read()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"Applied migration: {args.path}")


if __name__ == "__main__":
    main()
