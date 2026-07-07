from pathlib import Path

from alembic.config import Config


def test_alembic_configuration_points_to_backend_migrations():
    root_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(root_dir / "alembic.ini"))

    assert alembic_cfg.get_main_option("script_location") == "backend/alembic"
    assert (root_dir / "backend" / "alembic" / "env.py").exists()
    assert (root_dir / "backend" / "alembic" / "versions" / "0001_create_project_and_analysis_result_tables.py").exists()
    assert (root_dir / "backend" / "alembic" / "versions" / "0002_create_legal_reference_tables.py").exists()
    assert (root_dir / "backend" / "alembic" / "versions" / "0003_create_law_update_events.py").exists()
