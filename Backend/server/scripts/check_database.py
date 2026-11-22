import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import engine


def main() -> int:
    failed = False
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ).scalars()
        for table in tables:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
            print(f"{table}: {count}")

        missing_ai = conn.execute(
            text("SELECT COUNT(*) FROM foods WHERE ai_label IS NULL OR ai_label=''")
        ).scalar_one()
        bad_bbox = conn.execute(
            text(
                "SELECT COUNT(*) FROM restaurants "
                "WHERE lat < 15.9 OR lat > 16.2 OR lng < 107.9 OR lng > 108.35"
            )
        ).scalar_one()
        print(f"foods_missing_ai: {missing_ai}")
        print(f"restaurants_bad_bbox: {bad_bbox}")
        failed |= missing_ai != 0 or bad_bbox != 0

    for slot in ("breakfast", "lunch", "snack", "dinner"):
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM restaurants "
                    "WHERE is_active=1 AND instr(',' || meal_slots || ',', ',' || :slot || ',') > 0"
                ),
                {"slot": slot},
            ).scalar_one()
        print(f"active_restaurants_{slot}: {count}")
        failed |= count < 8
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
