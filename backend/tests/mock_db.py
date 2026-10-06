"""Shared mock-session helper for endpoint tests.

Route handlers call ``db.execute(...)`` more than once: first
``get_current_user`` resolves the caller, then the handler loads the company.
A single MagicMock cannot distinguish those calls, so this queues scalar
results per ``execute`` call.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


class MockSession:
    """AsyncMock session whose scalar results can be queued per call."""

    def __init__(self):
        self._queue: list = []
        self.scalar_value: object = None
        self.scalars_value: list = []
        self.execute = AsyncMock(side_effect=self._execute)
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.add = MagicMock()
        self.refresh = AsyncMock()

    def queue(self, *values):
        """Queue scalar results, returned one per ``execute`` call."""
        self._queue.extend(values)
        return self

    def set_scalar(self, value):
        """Value returned by ``result.scalar()`` (COUNT queries)."""
        self.scalar_value = value
        return self

    async def _execute(self, *_args, **_kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = self._queue.pop(0) if self._queue else None
        result.scalar.return_value = self.scalar_value
        result.scalars.return_value.all.return_value = self.scalars_value
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False
