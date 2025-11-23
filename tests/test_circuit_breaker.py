"""
Tests for Circuit Breaker module.

Tests cover:
- State transitions (CLOSED -> OPEN -> HALF_OPEN)
- Failure counting
- Timeout reset
- Manual reset
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.circuit_breaker import CircuitBreaker


# =============================================================================
# Basic State Tests
# =============================================================================

class TestCircuitBreakerBasic:
    """Tests for basic circuit breaker functionality."""

    def test_initial_state_closed(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_can_execute_when_closed(self):
        """Should allow execution when circuit is closed."""
        cb = CircuitBreaker()
        can_execute, reason = cb.can_execute()
        assert can_execute is True
        assert "closed" in reason.lower()

    def test_record_success_resets_count(self):
        """Success should reset failure count."""
        cb = CircuitBreaker()
        cb.failure_count = 3
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "CLOSED"


# =============================================================================
# Failure Tests
# =============================================================================

class TestCircuitBreakerFailures:
    """Tests for failure handling."""

    def test_record_failure_increments_count(self):
        """Failure should increment failure count."""
        cb = CircuitBreaker(max_failures=5)
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == "CLOSED"

    def test_circuit_opens_after_max_failures(self):
        """Circuit should open after max failures."""
        cb = CircuitBreaker(max_failures=3)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "CLOSED"
        
        cb.record_failure()  # Third failure
        assert cb.state == "OPEN"
        assert cb.failure_count == 3

    def test_cannot_execute_when_open(self):
        """Should block execution when circuit is open."""
        cb = CircuitBreaker(max_failures=1)
        cb.record_failure()
        
        can_execute, reason = cb.can_execute()
        assert can_execute is False
        assert "OPEN" in reason

    def test_failure_sets_last_failure_time(self):
        """Failure should set last_failure_time."""
        cb = CircuitBreaker()
        assert cb.last_failure_time is None
        
        cb.record_failure()
        assert cb.last_failure_time is not None


# =============================================================================
# Timeout and Half-Open Tests
# =============================================================================

class TestCircuitBreakerTimeout:
    """Tests for timeout and half-open state."""

    def test_circuit_transitions_to_half_open_after_timeout(self):
        """Circuit should transition to HALF_OPEN after timeout."""
        cb = CircuitBreaker(max_failures=1, reset_timeout_minutes=1)
        cb.record_failure()
        assert cb.state == "OPEN"
        
        # Simulate timeout elapsed
        cb.last_failure_time = datetime.utcnow() - timedelta(minutes=2)
        
        can_execute, reason = cb.can_execute()
        assert can_execute is True
        assert cb.state == "HALF_OPEN"
        assert "half-open" in reason.lower()

    def test_success_in_half_open_closes_circuit(self):
        """Success in HALF_OPEN should close circuit."""
        cb = CircuitBreaker()
        cb.state = "HALF_OPEN"
        cb.failure_count = 5
        
        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_failure_in_half_open_reopens_circuit(self):
        """Failure in HALF_OPEN should reopen circuit."""
        cb = CircuitBreaker(max_failures=1)
        cb.state = "HALF_OPEN"
        cb.failure_count = 0
        
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.failure_count == 1


# =============================================================================
# Reset Tests
# =============================================================================

class TestCircuitBreakerReset:
    """Tests for manual reset functionality."""

    def test_manual_reset(self):
        """Manual reset should restore initial state."""
        cb = CircuitBreaker(max_failures=1)
        cb.record_failure()
        assert cb.state == "OPEN"
        
        cb.reset()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None

    def test_get_status(self):
        """get_status should return current state info."""
        cb = CircuitBreaker(max_failures=3, reset_timeout_minutes=15)
        cb.record_failure()
        
        status = cb.get_status()
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 1
        assert status["max_failures"] == 3
        assert status["reset_timeout_minutes"] == 15
        assert status["last_failure_time"] is not None


# =============================================================================
# Configuration Tests
# =============================================================================

class TestCircuitBreakerConfig:
    """Tests for configuration options."""

    def test_custom_max_failures(self):
        """Should respect custom max_failures."""
        cb = CircuitBreaker(max_failures=10)
        
        for i in range(9):
            cb.record_failure()
            assert cb.state == "CLOSED"
        
        cb.record_failure()  # 10th failure
        assert cb.state == "OPEN"

    def test_custom_reset_timeout(self):
        """Should respect custom reset_timeout_minutes."""
        cb = CircuitBreaker(max_failures=1, reset_timeout_minutes=60)
        cb.record_failure()
        
        # 30 minutes elapsed - not enough
        cb.last_failure_time = datetime.utcnow() - timedelta(minutes=30)
        can_execute, reason = cb.can_execute()
        assert can_execute is False
        
        # 61 minutes elapsed - should be half-open
        cb.last_failure_time = datetime.utcnow() - timedelta(minutes=61)
        can_execute, reason = cb.can_execute()
        assert can_execute is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
