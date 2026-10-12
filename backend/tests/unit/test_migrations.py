"""Migrations must at least generate offline SQL (catches metadata errors in CI)."""

from pathlib import Path

from alembic.config import Config

from alembic import command


def test_upgrade_head_generates_offline_sql(capsys):
    backend = Path(__file__).parents[2]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(cfg, "head", sql=True)
    out = capsys.readouterr().out
    assert "CREATE TABLE" in out
