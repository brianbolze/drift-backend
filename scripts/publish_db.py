"""Publish the production database to Cloudflare R2 for OTA updates.

Uploads drift.db and manifest.json to the drift-data R2 bucket.
Validates primary key stability against the previously published version
to ensure no user-referenced IDs are removed or reassigned.

Usage:
    python scripts/publish_db.py --changelog "Added 47 Berger bullets"
    python scripts/publish_db.py --dry-run --changelog "Preview only"
    python scripts/publish_db.py --db path/to/drift.db --changelog "..."
    python scripts/publish_db.py --skip-pk-check --changelog "First publish"

Environment variables (loaded from .env):
    R2_ACCESS_KEY_ID      Cloudflare R2 access key
    R2_SECRET_ACCESS_KEY  Cloudflare R2 secret key
    R2_ENDPOINT_URL       Cloudflare S3-compatible endpoint
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install -e '.[publish]'", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional — env vars can be set directly

import os

# ── Configuration ────────────────────────────────────────────────────────────

SCHEMA_VERSION = 1  # Bump when production DB schema changes incompatibly
R2_BUCKET = "drift-data"
PRODUCTION_DB = Path("data/production/drift.db")
PK_CHECK_TABLES = ["bullet", "cartridge", "rifle_model"]


# ── Helpers ──────────────────────────────────────────────────────────────────


def sha256_file(path: Path) -> str:
    """Compute hex-encoded SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_primary_keys(db_path: Path, table: str) -> set[str]:
    """Return all primary key (id) values from a table."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"SELECT id FROM [{table}]").fetchall()  # noqa: S608
        return {row[0] for row in rows}
    finally:
        conn.close()


def get_s3_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    endpoint = os.environ.get("R2_ENDPOINT_URL")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    missing = []
    if not endpoint:
        missing.append("R2_ENDPOINT_URL")
    if not access_key:
        missing.append("R2_ACCESS_KEY_ID")
    if not secret_key:
        missing.append("R2_SECRET_ACCESS_KEY")

    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Set them in .env or export them directly.", file=sys.stderr)
        sys.exit(1)

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def fetch_current_manifest(s3) -> dict | None:
    """Fetch the current manifest.json from R2. Returns None if not found."""
    try:
        response = s3.get_object(Bucket=R2_BUCKET, Key="manifest.json")
        return json.loads(response["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def download_current_db(s3, dest: Path) -> bool:
    """Download the current drift.db from R2. Returns False if not found."""
    try:
        s3.download_file(R2_BUCKET, "drift.db", str(dest))
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return False
        raise


# ── Primary Key Stability Check ─────────────────────────────────────────────


def check_pk_stability(old_db: Path, new_db: Path) -> list[str]:
    """Compare primary keys between old and new DB. Returns list of errors."""
    errors = []
    for table in PK_CHECK_TABLES:
        old_keys = get_primary_keys(old_db, table)
        new_keys = get_primary_keys(new_db, table)
        missing = old_keys - new_keys
        if missing:
            errors.append(f"  {table}: {len(missing)} PKs removed: {sorted(missing)[:10]}")
            if len(missing) > 10:
                errors[-1] += f" ... and {len(missing) - 10} more"
        added = new_keys - old_keys
        if added:
            print(f"  {table}: {len(added)} new PKs (OK)")
        if not missing and not added:
            print(f"  {table}: {len(old_keys)} PKs unchanged (OK)")
    return errors


# ── Main ─────────────────────────────────────────────────────────────────────


def run_pk_stability_check(s3, db_path: Path, skip: bool, has_manifest: bool) -> None:
    """Validate that no primary keys were removed between the published and new DB."""
    if skip:
        print("\nPrimary key check: SKIPPED (--skip-pk-check)")
        return

    if not has_manifest or not s3:
        print("\nPrimary key check: skipped (first publish)")
        return

    print("\nRunning primary key stability check...")
    with tempfile.TemporaryDirectory() as tmpdir:
        old_db_path = Path(tmpdir) / "old_drift.db"
        if not download_current_db(s3, old_db_path):
            print("  No existing DB on R2 — skipping PK check")
            return

        errors = check_pk_stability(old_db_path, db_path)
        if errors:
            print("\nERROR: Primary key stability check FAILED!", file=sys.stderr)
            print("The following primary keys were removed:", file=sys.stderr)
            for err in errors:
                print(err, file=sys.stderr)
            print("\nThis would break user profiles referencing these IDs.", file=sys.stderr)
            print("Use --skip-pk-check to override (dangerous).", file=sys.stderr)
            sys.exit(1)
        print("  All primary keys stable.")


def upload_to_r2(s3, db_path: Path, manifest: dict) -> None:
    """Upload drift.db and manifest.json to R2 (DB first, manifest second)."""
    db_size = db_path.stat().st_size
    print(f"\nUploading {db_path.name} ({db_size / 1024:.0f} KB)...")
    s3.upload_file(
        str(db_path),
        R2_BUCKET,
        "drift.db",
        ExtraArgs={"ContentType": "application/x-sqlite3"},
    )
    print("  drift.db uploaded.")

    print("Uploading manifest.json...")
    s3.put_object(
        Bucket=R2_BUCKET,
        Key="manifest.json",
        Body=json.dumps(manifest, indent=2),
        ContentType="application/json",
    )
    print("  manifest.json uploaded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish production database to Cloudflare R2")
    parser.add_argument("--db", default=str(PRODUCTION_DB), help=f"Path to production DB (default: {PRODUCTION_DB})")
    parser.add_argument("--changelog", required=True, help="Human-readable changelog for this version")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without uploading")
    parser.add_argument("--skip-pk-check", action="store_true", help="Skip primary key stability check")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        print("Run 'make export-production-db' first.", file=sys.stderr)
        sys.exit(1)

    # ── Connect to R2 ────────────────────────────────────────────────────
    if not args.dry_run:
        s3 = get_s3_client()
    else:
        try:
            s3 = get_s3_client()
        except SystemExit:
            print("WARN: R2 credentials not set — skipping remote manifest fetch for dry-run")
            s3 = None

    # ── Fetch current manifest ───────────────────────────────────────────
    current_manifest = None
    if s3:
        print("Fetching current manifest from R2...")
        current_manifest = fetch_current_manifest(s3)

    if current_manifest:
        current_version = current_manifest["version"]
        print(f"  Current version: {current_version}")
        print(f"  Published at: {current_manifest.get('published_at', 'unknown')}")
    else:
        current_version = 0
        print("  No existing manifest — this will be the first publish (version 1)")

    new_version = current_version + 1

    # ── Primary key stability check ──────────────────────────────────────
    run_pk_stability_check(s3, db_path, args.skip_pk_check, current_manifest is not None)

    # ── Build manifest ───────────────────────────────────────────────────
    db_hash = sha256_file(db_path)
    db_size = db_path.stat().st_size

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "version": new_version,
        "sha256": db_hash,
        "size_bytes": db_size,
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "changelog": args.changelog,
    }

    print(f"\nManifest for version {new_version}:")
    print(json.dumps(manifest, indent=2))

    # ── Upload ───────────────────────────────────────────────────────────
    if args.dry_run:
        print("\nDRY RUN — nothing uploaded.")
        print(f"Would upload: {db_path.name} ({db_size / 1024:.0f} KB) + manifest.json")
        return

    upload_to_r2(s3, db_path, manifest)
    print(f"\nPublished version {new_version} to {R2_BUCKET}")
    print("  URL: https://data.driftballistics.com/manifest.json")
    print("  URL: https://data.driftballistics.com/drift.db")


if __name__ == "__main__":
    main()
