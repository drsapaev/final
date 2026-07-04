"""
Seed default AI feature flags into the database.

The feature_flags infrastructure (services + endpoints + admin UI) is fully
built but was not actually USED by any AI endpoint. This seeder creates the
default flag set so admins can toggle AI features on/off without code deploys.

Usage:
    cd backend && python -m app.scripts.seed_ai_feature_flags

    # Or to reset to defaults (delete + recreate)
    cd backend && python -m app.scripts.seed_ai_feature_flags --reset

Default flags created:
    ai_complaint_analysis    — /ai-gateway/analyze-complaints
    ai_icd10_suggestion      — /ai-gateway/suggest-icd10
    ai_smart_template        — /emr-ai-enhanced/generate-smart-template
    ai_smart_suggestions     — /emr-ai-enhanced/smart-suggestions
    ai_chat_assistant        — /ai-chat endpoints
    ai_phrase_suggest        — /phrase-suggest endpoint

All default to enabled=True in 'all' environments. Admins can disable
per-environment via the admin panel or API.

Safety:
- Idempotent — re-running won't duplicate flags.
- --reset deletes the listed flags + their history, then recreates.
- Refuses to run against DB names containing 'prod' unless --confirm-prod.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
log = logging.getLogger("seed_ai_flags")

# ---------------------------------------------------------------------------
# Flag definitions
# ---------------------------------------------------------------------------

DEFAULT_FLAGS: list[dict[str, Any]] = [
    {
        "key": "ai_complaint_analysis",
        "name": "AI Complaint Analysis",
        "description": "POST /ai-gateway/analyze-complaints — AI generates examination plan from patient complaints. Disabling returns 503 to all callers.",
        "enabled": True,
        "category": "ai_clinical",
        "environment": "all",
        "config": {"provider": "auto", "fallback_message": "AI analysis disabled by admin"},
    },
    {
        "key": "ai_icd10_suggestion",
        "name": "AI ICD-10 Suggestion",
        "description": "POST /ai-gateway/suggest-icd10 — AI suggests ICD-10 codes from symptoms. Disabling returns 503.",
        "enabled": True,
        "category": "ai_clinical",
        "environment": "all",
        "config": {"provider": "auto"},
    },
    {
        "key": "ai_smart_template",
        "name": "AI Smart EMR Template",
        "description": "POST /emr-ai-enhanced/generate-smart-template — AI generates specialty-aware EMR templates. Disabling returns 503.",
        "enabled": True,
        "category": "ai_clinical",
        "environment": "all",
        "config": {"provider": "auto"},
    },
    {
        "key": "ai_smart_suggestions",
        "name": "AI Smart Field Suggestions",
        "description": "POST /emr-ai-enhanced/smart-suggestions — AI suggests field-level values in EMR. Disabling returns 503.",
        "enabled": True,
        "category": "ai_clinical",
        "environment": "all",
        "config": {"provider": "auto"},
    },
    {
        "key": "ai_chat_assistant",
        "name": "AI Chat Assistant",
        "description": "All /ai-chat endpoints — conversational AI assistant for doctors. Disabling returns 503.",
        "enabled": True,
        "category": "ai_chat",
        "environment": "all",
        "config": {"provider": "auto", "rate_limit_per_hour": 100},
    },
    {
        "key": "ai_phrase_suggest",
        "name": "AI Phrase Suggestion",
        "description": "POST /phrase-suggest — inline phrase suggestions in EMR editor. Disabling returns 503.",
        "enabled": True,
        "category": "ai_clinical",
        "environment": "all",
        "config": {"provider": "auto"},
    },
    # Non-AI flags worth seeding
    {
        "key": "telegram_mini_app_enabled",
        "name": "Telegram Mini App",
        "description": "Patient-facing Telegram mini-app. Disabling hides the patient shell.",
        "enabled": True,
        "category": "integration",
        "environment": "all",
        "config": {},
    },
    {
        "key": "online_queue_enabled",
        "name": "Online Queue Booking",
        "description": "Patient self-service online queue booking. Disabling hides the queue-join page.",
        "enabled": True,
        "category": "core",
        "environment": "all",
        "config": {"max_per_day_per_department": 15},
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed default AI feature flags.")
    parser.add_argument("--reset", action="store_true", help="Delete listed flags + history, then recreate.")
    parser.add_argument("--confirm-prod", action="store_true", help="Allow running against prod DB names.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args(argv)

    if not args.database_url:
        log.error("DATABASE_URL not set.")
        return 2

    if "prod" in args.database_url.lower() and not args.confirm_prod:
        log.error("Refusing to seed prod DB without --confirm-prod.")
        return 2

    engine = create_engine(args.database_url)
    db = Session(engine)

    try:
        if args.reset:
            log.info("Reset mode: deleting listed flags + history...")
            for flag in DEFAULT_FLAGS:
                db.execute(text("DELETE FROM feature_flag_history WHERE flag_key = :k"), {"k": flag["key"]})
                db.execute(text("DELETE FROM feature_flags WHERE key = :k"), {"k": flag["key"]})
            db.commit()
            log.info("Reset complete.")

        # Check if feature_flags table exists
        exists = db.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'feature_flags')"
        )).scalar()
        if not exists:
            log.error("Table 'feature_flags' does not exist. Run alembic upgrade head first.")
            return 2

        created = 0
        skipped = 0
        for flag in DEFAULT_FLAGS:
            existing = db.execute(text("SELECT id FROM feature_flags WHERE key = :k"), {"k": flag["key"]}).first()
            if existing:
                log.info("  skip (exists): %s", flag["key"])
                skipped += 1
                continue

            db.execute(text("""
                INSERT INTO feature_flags
                    (key, name, description, enabled, config, category, environment, created_at)
                VALUES
                    (:key, :name, :description, :enabled, CAST(:config AS JSONB), :category, :environment, NOW())
            """), {
                "key": flag["key"],
                "name": flag["name"],
                "description": flag["description"],
                "enabled": flag["enabled"],
                "config": __import__("json").dumps(flag["config"]),
                "category": flag["category"],
                "environment": flag["environment"],
            })
            db.commit()
            log.info("  created: %s", flag["key"])
            created += 1

        log.info("Done. Created %d, skipped %d (already existed).", created, skipped)
        log.info("Toggle via admin panel or: PUT /api/v1/admin/feature-flags/{key}")
        return 0
    except Exception as e:
        db.rollback()
        log.exception("Seed failed: %s", e)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
