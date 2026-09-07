"""Tests for database initialization and migration helpers."""

from unittest.mock import patch

from app.database import run_migrations


def test_run_migrations_calls_alembic_upgrade_head():
    """run_migrations should call alembic upgrade head with the database URL."""
    with (
        patch("alembic.config.Config", autospec=True) as mock_cfg_cls,
        patch("alembic.command") as mock_command,
    ):
        mock_cfg = mock_cfg_cls.return_value
        run_migrations("postgresql+asyncpg://user:pass@localhost/test")

        mock_cfg.set_main_option.assert_called_once_with(
            "sqlalchemy.url", "postgresql+asyncpg://user:pass@localhost/test"
        )
        mock_command.upgrade.assert_called_once_with(mock_cfg, "head")
