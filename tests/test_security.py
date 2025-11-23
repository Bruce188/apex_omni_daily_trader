"""
Security-focused tests for ApexOmni Trading Bot.

Tests cover:
- Path traversal prevention
- Error sanitization
- Mainnet warning
- Circuit breaker integration
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.storage import Storage, PROJECT_ROOT as STORAGE_PROJECT_ROOT
from bot.utils import warn_if_live_mainnet


# =============================================================================
# Path Traversal Prevention Tests
# =============================================================================

class TestPathTraversalPrevention:
    """Tests for path traversal attack prevention."""

    def test_valid_project_path(self):
        """Should accept paths within project root."""
        with tempfile.TemporaryDirectory(prefix="apex_test_", dir=str(PROJECT_ROOT)) as temp_dir:
            storage = Storage(data_dir=temp_dir)
            assert storage.data_dir == Path(temp_dir).resolve()

    def test_valid_tmp_path(self):
        """Should accept paths within /tmp."""
        with tempfile.TemporaryDirectory(prefix="apex_test_") as temp_dir:
            storage = Storage(data_dir=temp_dir)
            assert storage.data_dir == Path(temp_dir).resolve()

    def test_reject_outside_allowed_paths(self):
        """Should reject paths outside allowed prefixes."""
        # Try to create storage with path outside allowed prefixes
        # This simulates an attacker trying path traversal
        with pytest.raises(ValueError) as exc_info:
            Storage(data_dir="/etc/passwd/../../../home/attacker")
        
        assert "not allowed" in str(exc_info.value).lower()

    def test_reject_absolute_path_traversal(self):
        """Should reject absolute path traversal attempts."""
        with pytest.raises(ValueError) as exc_info:
            Storage(data_dir="/var/log")
        
        assert "not allowed" in str(exc_info.value).lower()


# =============================================================================
# Error Sanitization Tests
# =============================================================================

class TestErrorSanitization:
    """Tests for error message sanitization."""

    def test_api_client_error_sanitization_mainnet(self):
        """Should sanitize errors on mainnet without DEBUG."""
        from bot.api_client import ApexOmniClient
        from bot.config import APIConfig
        
        config = APIConfig(
            api_key="test",
            api_secret="test",
            passphrase="test",
            testnet=False,  # Mainnet
        )
        
        client = ApexOmniClient(config)
        
        # Mock environment without DEBUG
        with patch.dict(os.environ, {"DEBUG": ""}):
            assert client._should_include_error_details() is False

    def test_api_client_error_details_testnet(self):
        """Should include error details on testnet."""
        from bot.api_client import ApexOmniClient
        from bot.config import APIConfig
        
        config = APIConfig(
            api_key="test",
            api_secret="test",
            passphrase="test",
            testnet=True,  # Testnet
        )
        
        client = ApexOmniClient(config)
        assert client._should_include_error_details() is True

    def test_api_client_error_details_debug_mode(self):
        """Should include error details when DEBUG=true."""
        from bot.api_client import ApexOmniClient
        from bot.config import APIConfig
        
        config = APIConfig(
            api_key="test",
            api_secret="test",
            passphrase="test",
            testnet=False,  # Mainnet
        )
        
        client = ApexOmniClient(config)
        
        with patch.dict(os.environ, {"DEBUG": "true"}):
            assert client._should_include_error_details() is True


# =============================================================================
# Mainnet Warning Tests
# =============================================================================

class TestMainnetWarning:
    """Tests for mainnet warning functionality."""

    def test_no_warning_dry_run(self):
        """Should not show warning in dry run mode."""
        mock_config = Mock()
        mock_config.safety.dry_run = True
        mock_config.api.testnet = False
        mock_logger = Mock()
        
        result = warn_if_live_mainnet(mock_config, mock_logger)
        
        assert result is True
        mock_logger.warning.assert_not_called()

    def test_no_warning_testnet(self):
        """Should not show warning on testnet."""
        mock_config = Mock()
        mock_config.safety.dry_run = False
        mock_config.api.testnet = True
        mock_logger = Mock()
        
        result = warn_if_live_mainnet(mock_config, mock_logger)
        
        assert result is True
        mock_logger.warning.assert_not_called()

    def test_warning_shown_mainnet_live(self):
        """Should show warning on mainnet in live mode."""
        mock_config = Mock()
        mock_config.safety.dry_run = False
        mock_config.api.testnet = False
        mock_logger = Mock()
        
        # Simulate immediate KeyboardInterrupt
        with patch('bot.utils.time.sleep', side_effect=KeyboardInterrupt):
            result = warn_if_live_mainnet(mock_config, mock_logger)
        
        assert result is False
        mock_logger.warning.assert_called_once()
        mock_logger.info.assert_called_once()


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================

class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration in trade executor."""

    def test_trade_executor_has_circuit_breaker(self, trade_executor):
        """Trade executor should have circuit breaker."""
        from bot.circuit_breaker import CircuitBreaker
        assert hasattr(trade_executor, 'circuit_breaker')
        assert isinstance(trade_executor.circuit_breaker, CircuitBreaker)

    def test_trade_blocked_when_circuit_open(self, trade_executor, sample_executor_trade):
        """Should block trades when circuit is open."""
        # Open the circuit breaker
        trade_executor.circuit_breaker.state = "OPEN"
        trade_executor.circuit_breaker.failure_count = 5
        
        result = trade_executor.execute_trade(sample_executor_trade)
        
        assert result.success is False
        assert "circuit breaker" in result.error.lower()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def trade_executor():
    """Create a trade executor with mock client."""
    from bot.trade_executor import TradeExecutor
    from bot.api_client import MockApexOmniClient
    from bot.config import Config, APIConfig, TradingConfig, SafetyConfig, ScheduleConfig
    from decimal import Decimal
    import tempfile
    
    with tempfile.TemporaryDirectory(prefix="apex_test_") as temp_dir:
        config = Config(
            api=APIConfig(
                api_key="test",
                api_secret="test",
                passphrase="test",
                testnet=True,
            ),
            trading=TradingConfig(
                symbol="BTC-USDT",
                side="BUY",
                order_type="MARKET",
                size=Decimal("0.001"),
            ),
            safety=SafetyConfig(
                dry_run=True,
                max_retries=3,
                retry_delay=0.01,
            ),
            schedule=ScheduleConfig(),
            data_dir=temp_dir,
        )
        
        client = MockApexOmniClient(config.api)
        yield TradeExecutor(client=client, config=config)


@pytest.fixture
def sample_executor_trade():
    """Create a sample trade."""
    from bot.trade_executor import Trade
    from decimal import Decimal
    
    return Trade(
        symbol="BTC-USDT",
        side="BUY",
        order_type="MARKET",
        size=Decimal("0.001"),
        price=Decimal("95000.0"),
        day_number=1,
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
