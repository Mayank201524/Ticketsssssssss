from datetime import datetime

import pytest
from pydantic import ValidationError

from tickets_gen.models import Change, ChangeSource


def test_change_rejects_naive_datetime():
    with pytest.raises(ValidationError, match="timezone-aware"):
        Change(
            source=ChangeSource.GITHUB,
            repository="acme/api",
            sha="abcdef123",
            message="test",
            authored_at=datetime(2026, 1, 1),
            committed_at=datetime(2026, 1, 1),
            html_url="https://example.com",
        )
