import json

from app.core.database import SessionLocal
from app.services.dev_seed_service import seed_demo_data


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_demo_data(db)
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        db.close()


if __name__ == "__main__":
    main()
