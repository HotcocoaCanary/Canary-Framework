"""Unit tests for engine.logging module."""

import pytest

from canary_framework.engine.logging import ensure_logging, get_logger


@pytest.mark.unit
class TestLogging:
    """Tests for logging functions."""

    def test_get_logger(self) -> None:
        """Test get_logger returns a logger."""
        logger = get_logger("test")
        assert logger is not None
        assert logger.name == "cf.test"

    def test_ensure_logging(self) -> None:
        """Test ensure_logging can be called multiple times."""
        ensure_logging("INFO")
        # Should not raise
        ensure_logging("DEBUG")
