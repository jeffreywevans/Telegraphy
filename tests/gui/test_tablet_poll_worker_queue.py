from __future__ import annotations

from unittest.mock import MagicMock

from telegraphy.gui import tablet_app


def test_poll_worker_queue_returns_without_side_effects_when_worker_is_inactive(monkeypatch):
    tablet = tablet_app.TelegraphyTablet.__new__(tablet_app.TelegraphyTablet)
    tablet._worker_active = False
    tablet.result_queue = MagicMock()

    after = MagicMock()
    monkeypatch.setattr(tablet, "after", after)

    tablet._poll_worker_queue()

    tablet.result_queue.get_nowait.assert_not_called()
    after.assert_not_called()
    assert tablet._worker_active is False
