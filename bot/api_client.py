"""
ApexOmni API Client.

Handles authentication, API requests, and response handling
for the ApexOmni exchange.
"""

import os
import time
from decimal import Decimal
from typing import Optional, Any
from dataclasses import dataclass

from bot.config import APIConfig
from bot.utils import get_logger, mask_api_key, parse_decimal


@dataclass
class AccountBalance:
    """Account balance information."""
    total_equity: Decimal
    available_balance: Decimal
    margin_balance: Decimal
    unrealized_pnl: Decimal


@dataclass
class SymbolConfig:
    """Trading symbol configuration."""
    symbol: str
    base_currency: str
    quote_currency: str
    min_order_size: Decimal
    tick_size: Decimal
    step_size: Decimal
    max_leverage: int
    enable_open_position: bool = True  # Whether new positions can be opened
    enable_trade: bool = True  # Whether trading is enabled


@dataclass
class OrderResult:
    """Result of an order placement."""
    success: bool
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    size: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    filled_size: Decimal = Decimal("0")
    filled_price: Decimal = Decimal("0")
    status: str = ""
    fee: Decimal = Decimal("0")
    timestamp: int = 0
    error: Optional[str] = None


class ApexOmniClient:
    """
    Client for interacting with the ApexOmni API.

    Uses the official apexomni SDK for authentication and API calls.
    """

    def __init__(self, config: APIConfig):
        """
        Initialize the API client.

        Args:
            config: API configuration with credentials
        """
        self.config = config
        self.logger = get_logger()
        self._client = None
        self._configs_cache = None
        self._account_cache = None
        self._sdk_initialized = False  # Track if SDK configV3/accountV3 are set
        self._initialized = False

    def _should_include_error_details(self) -> bool:
        """
        Determine if error details should be included in logs.

        In production (mainnet, not debug), sanitizes error messages.
        In development (testnet or DEBUG=true), includes full details.
        """
        return self.config.testnet or os.getenv("DEBUG", "").lower() == "true"

    def _log_error(
        self,
        message: str,
        exception: Optional[Exception] = None,
        include_details: Optional[bool] = None
    ) -> None:
        """
        Log error with appropriate detail level.

        Args:
            message: Base error message
            exception: Optional exception to log details from
            include_details: Override for including details (None = auto-detect)
        """
        if include_details is None:
            include_details = self._should_include_error_details()

        if include_details and exception:
            self.logger.error(f"{message}: {exception}")
        elif exception:
            self.logger.error(f"{message}. Enable DEBUG=true for details.")
        else:
            self.logger.error(message)

    def _get_client(self):
        """
        Get or create the SDK client.

        Lazy initialization to handle import errors gracefully.
        """
        if self._client is not None:
            return self._client

        try:
            # Try to import the SDK
            if self.config.zk_seeds:
                # Use signing client for trading
                from apexomni.http_private_sign import HttpPrivateSign

                if self.config.testnet:
                    from apexomni.constants import APEX_OMNI_HTTP_TEST, NETWORKID_TEST
                    endpoint = APEX_OMNI_HTTP_TEST
                    network_id = NETWORKID_TEST
                else:
                    from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_MAIN
                    endpoint = APEX_OMNI_HTTP_MAIN
                    network_id = NETWORKID_MAIN

                self._client = HttpPrivateSign(
                    endpoint,
                    network_id=network_id,
                    zk_seeds=self.config.zk_seeds,
                    zk_l2Key=self.config.zk_l2key or '',
                    api_key_credentials={
                        'key': self.config.api_key,
                        'secret': self.config.api_secret,
                        'passphrase': self.config.passphrase
                    }
                )
            else:
                # Use read-only client (no trading)
                from apexomni.http_private_v3 import HttpPrivate_v3

                if self.config.testnet:
                    from apexomni.constants import APEX_OMNI_HTTP_TEST, NETWORKID_TEST
                    endpoint = APEX_OMNI_HTTP_TEST
                    network_id = NETWORKID_TEST
                else:
                    from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_MAIN
                    endpoint = APEX_OMNI_HTTP_MAIN
                    network_id = NETWORKID_MAIN

                self._client = HttpPrivate_v3(
                    endpoint,
                    network_id=network_id,
                    api_key_credentials={
                        'key': self.config.api_key,
                        'secret': self.config.api_secret,
                        'passphrase': self.config.passphrase
                    }
                )

            self._initialized = True
            self.logger.info(f"API client initialized for {self.config.network}")

        except ImportError as e:
            self._log_error("Failed to import apexomni SDK", e)
            self.logger.error("Install with: pip install apexomni")
            raise
        except Exception as e:
            self._log_error("Failed to initialize API client", e)
            raise

        return self._client

    def _ensure_sdk_initialized(self) -> bool:
        """
        Ensure the SDK client has configV3 and accountV3 set.

        The ApexOmni SDK requires configs_v3() and get_account_v3() to be called
        BEFORE placing orders, as these populate self.configV3 and self.accountV3
        which are required for order signing.

        Returns:
            bool: True if SDK is properly initialized
        """
        if self._sdk_initialized:
            return True

        try:
            client = self._get_client()

            # Call configs_v3() to set configV3
            if not self._configs_cache:
                configs = client.configs_v3()
                if configs and 'data' in configs:
                    self._configs_cache = configs
                else:
                    self.logger.error("Failed to initialize SDK configs")
                    return False

            # Call get_account_v3() to set accountV3
            if not self._account_cache:
                account = client.get_account_v3()
                if account:
                    self._account_cache = account
                else:
                    self.logger.error("Failed to initialize SDK account")
                    return False

            self._sdk_initialized = True
            self.logger.debug("SDK initialized with configV3 and accountV3")
            return True

        except Exception as e:
            self._log_error("Failed to initialize SDK", e)
            return False

    def test_connection(self) -> bool:
        """
        Test the API connection and initialize SDK for trading.

        Returns:
            bool: True if connection successful
        """
        try:
            client = self._get_client()

            # Get configs to test connection AND initialize SDK
            configs = client.configs_v3()

            if configs and 'data' in configs:
                self._configs_cache = configs
                self.logger.info("API connection test successful")

                # Also initialize account for trading capability
                try:
                    account = client.get_account_v3()
                    if account:
                        self._account_cache = account
                        self._sdk_initialized = True
                        self.logger.info("SDK fully initialized for trading")
                except Exception as e:
                    self.logger.warning(f"Account initialization failed: {e}")
                    # Connection test still passes, but trading may fail

                return True

            self.logger.warning("API connection test returned unexpected response")
            return False

        except Exception as e:
            self._log_error("API connection test failed", e)
            return False

    def get_configs(self) -> dict:
        """
        Get exchange configuration including symbol settings.

        Returns:
            dict: Exchange configuration data
        """
        if self._configs_cache:
            return self._configs_cache

        try:
            client = self._get_client()
            configs = client.configs_v3()
            self._configs_cache = configs
            return configs
        except Exception as e:
            self._log_error("Failed to get configs", e)
            raise

    def get_symbol_config(self, symbol: str) -> Optional[SymbolConfig]:
        """
        Get configuration for a specific trading symbol.

        Args:
            symbol: Trading symbol (e.g., "BTC-USDT")

        Returns:
            SymbolConfig or None if symbol not found
        """
        try:
            configs = self.get_configs()

            if not configs or 'data' not in configs:
                self.logger.error("No config data available")
                return None

            # Find symbol in perpetual contracts
            # API v3 structure: data -> contractConfig -> perpetualContract
            contract_config = configs.get('data', {}).get('contractConfig', {})
            perpetuals = contract_config.get('perpetualContract', [])

            for contract in perpetuals:
                if contract.get('symbol') == symbol:
                    return SymbolConfig(
                        symbol=contract['symbol'],
                        base_currency=contract.get('settleCurrencyId', '').replace('-', ''),
                        quote_currency=contract.get('underlyingCurrencyId', 'USDT'),
                        min_order_size=parse_decimal(contract.get('minOrderSize', '0.001')),
                        tick_size=parse_decimal(contract.get('tickSize', '0.1')),
                        step_size=parse_decimal(contract.get('stepSize', '0.001')),
                        max_leverage=int(contract.get('maxLeverage', 100)),
                        enable_open_position=contract.get('enableOpenPosition', True),
                        enable_trade=contract.get('enableTrade', True),
                    )

            self.logger.warning(f"Symbol {symbol} not found in configs")
            return None

        except Exception as e:
            self._log_error(f"Failed to get symbol config for {symbol}", e)
            return None

    def get_all_symbols(self, tradeable_only: bool = True) -> list[SymbolConfig]:
        """
        Get all available perpetual trading symbols with their configurations.

        Args:
            tradeable_only: If True, only return symbols where enableOpenPosition=True
                           and enableTrade=True (default). Set to False to get all symbols.

        Returns:
            List of SymbolConfig objects for all available perpetual contracts
        """
        try:
            configs = self.get_configs()

            if not configs or 'data' not in configs:
                self.logger.error("No config data available")
                return []

            # API v3 structure: data -> contractConfig -> perpetualContract
            contract_config = configs.get('data', {}).get('contractConfig', {})
            perpetuals = contract_config.get('perpetualContract', [])

            symbols = []
            skipped_disabled = 0
            for contract in perpetuals:
                try:
                    enable_open = contract.get('enableOpenPosition', True)
                    enable_trade = contract.get('enableTrade', True)

                    # Skip symbols that can't be traded if tradeable_only is True
                    if tradeable_only and (not enable_open or not enable_trade):
                        skipped_disabled += 1
                        continue

                    symbol_config = SymbolConfig(
                        symbol=contract['symbol'],
                        base_currency=contract.get('settleCurrencyId', '').replace('-', ''),
                        quote_currency=contract.get('underlyingCurrencyId', 'USDT'),
                        min_order_size=parse_decimal(contract.get('minOrderSize', '0.001')),
                        tick_size=parse_decimal(contract.get('tickSize', '0.1')),
                        step_size=parse_decimal(contract.get('stepSize', '0.001')),
                        max_leverage=int(contract.get('maxLeverage', 100)),
                        enable_open_position=enable_open,
                        enable_trade=enable_trade,
                    )
                    symbols.append(symbol_config)
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Skipping invalid contract: {e}")
                    continue

            if skipped_disabled > 0:
                self.logger.debug(f"Skipped {skipped_disabled} symbols with disabled trading")
            self.logger.info(f"Found {len(symbols)} tradeable symbols")
            return symbols

        except Exception as e:
            self._log_error("Failed to get all symbols", e)
            return []

    def get_account_balance(self) -> Optional[AccountBalance]:
        """
        Get account balance information.

        Returns:
            AccountBalance or None on error
        """
        try:
            client = self._get_client()
            account = client.get_account_v3()

            if not account:
                self.logger.error("Failed to get account data")
                return None

            # v3 API returns account data directly (not wrapped in 'data')
            # Get USDT balance from contract wallets for trading
            contract_wallets = account.get('contractWallets', [])
            usdt_balance = Decimal("0")
            for wallet in contract_wallets:
                if wallet.get('token') == 'USDT':
                    usdt_balance = parse_decimal(wallet.get('balance', '0'))
                    break

            # Calculate unrealized PnL from positions
            positions = account.get('positions', [])
            unrealized_pnl = Decimal("0")
            for pos in positions:
                unrealized_pnl += parse_decimal(pos.get('unrealizedPnl', '0'))

            # For margin trading, use USDT balance as available
            total_equity = usdt_balance + unrealized_pnl

            return AccountBalance(
                total_equity=total_equity,
                available_balance=usdt_balance,
                margin_balance=usdt_balance,
                unrealized_pnl=unrealized_pnl
            )

        except Exception as e:
            self._log_error("Failed to get account balance", e)
            return None

    def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current price or None on error
        """
        try:
            from apexomni.http_public import HttpPublic

            if self.config.testnet:
                from apexomni.constants import APEX_OMNI_HTTP_TEST
                endpoint = APEX_OMNI_HTTP_TEST
            else:
                from apexomni.constants import APEX_OMNI_HTTP_MAIN
                endpoint = APEX_OMNI_HTTP_MAIN

            public_client = HttpPublic(endpoint)
            ticker = public_client.ticker_v3(symbol=symbol)

            if ticker and 'data' in ticker:
                data = ticker['data']
                if isinstance(data, list) and len(data) > 0:
                    return parse_decimal(data[0].get('lastPrice', '0'))
                elif isinstance(data, dict):
                    return parse_decimal(data.get('lastPrice', '0'))

            return None

        except Exception as e:
            self._log_error(f"Failed to get current price for {symbol}", e)
            return None

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        size: Decimal,
        price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False
    ) -> OrderResult:
        """
        Place an order on the exchange.

        Args:
            symbol: Trading symbol (e.g., "BTC-USDT")
            side: Order side ("BUY" or "SELL")
            order_type: Order type ("MARKET" or "LIMIT")
            size: Order size
            price: Order price (required for limit orders, used as reference for market)
            client_order_id: Optional custom order ID
            reduce_only: Whether this order should only reduce position

        Returns:
            OrderResult with order details or error
        """
        try:
            client = self._get_client()

            # CRITICAL: Ensure SDK is initialized before placing orders
            # The SDK requires configV3 and accountV3 to be set
            if not self._ensure_sdk_initialized():
                return OrderResult(success=False, error="Failed to initialize SDK for trading")

            # Validate inputs
            if side.upper() not in ("BUY", "SELL"):
                return OrderResult(success=False, error=f"Invalid side: {side}")

            if order_type.upper() not in ("MARKET", "LIMIT"):
                return OrderResult(success=False, error=f"Invalid order type: {order_type}")

            # Get current price if not provided (needed for zkLink signature)
            if price is None:
                price = self.get_current_price(symbol)
                if price is None:
                    return OrderResult(success=False, error="Could not get current price")

            # Prepare order parameters
            # Note: clientOrderId is NOT supported by SDK v3's create_order_v3()
            order_params = {
                "symbol": symbol,
                "side": side.upper(),
                "type": order_type.upper(),
                "size": str(size),
                "price": str(price),
                "timestampSeconds": int(time.time()),
            }

            # Log client_order_id for our tracking but don't pass to SDK
            if client_order_id:
                self.logger.debug(f"Internal order tracking ID: {client_order_id}")

            if reduce_only:
                order_params["reduceOnly"] = True

            self.logger.info(f"Placing {order_type} {side} order: {size} {symbol} @ {price}")

            # Place the order
            response = client.create_order_v3(**order_params)

            if not response:
                return OrderResult(success=False, error="Empty response from API")

            # Check for explicit error response (has 'code' field with error)
            # Note: code can be int (3) or string ('3') depending on error type
            if 'code' in response:
                code = response['code']
                if code not in (0, '0', None):
                    error_msg = response.get('message', response.get('msg', 'Unknown error'))
                    error_key = response.get('key', '')
                    full_error = f"API Error: {error_msg}"
                    if error_key:
                        full_error += f" [{error_key}]"
                    return OrderResult(success=False, error=full_error)

            # Check for successful response (has 'data' with order 'id')
            data = response.get('data', {})
            if not data or not data.get('id'):
                return OrderResult(success=False, error="No order ID in response")

            self.logger.info(f"Order placed successfully: {data.get('id')}")

            return OrderResult(
                success=True,
                order_id=data.get('id', ''),
                client_order_id=data.get('clientOrderId', ''),
                symbol=symbol,
                side=side.upper(),
                order_type=order_type.upper(),
                size=size,
                price=price,
                filled_size=parse_decimal(data.get('filledSize', data.get('cumSuccessFillSize', '0'))),
                filled_price=parse_decimal(data.get('avgFillPrice', data.get('averagePrice', str(price)))),
                status=data.get('status', 'PENDING'),
                fee=parse_decimal(data.get('fee', data.get('cumSuccessFillFee', '0'))),
                timestamp=int(data.get('createdAt', time.time() * 1000))
            )

        except Exception as e:
            self._log_error("Failed to place order", e)
            # Return sanitized error for external consumption
            error_msg = str(e) if self._should_include_error_details() else "Order placement failed"
            return OrderResult(success=False, error=error_msg)

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancellation successful
        """
        try:
            client = self._get_client()
            response = client.delete_order_v3(id=order_id)

            if response and response.get('code') == '0':
                self.logger.info(f"Order {order_id} cancelled successfully")
                return True

            error_msg = response.get('message', 'Unknown error') if response else 'No response'
            self.logger.error(f"Failed to cancel order {order_id}: {error_msg}")
            return False

        except Exception as e:
            self._log_error(f"Failed to cancel order {order_id}", e)
            return False

    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """
        Get all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        try:
            client = self._get_client()

            params = {}
            if symbol:
                params['symbol'] = symbol

            response = client.open_orders_v3(**params)

            # Handle various API response formats
            if response is None:
                return []

            # If response is already a list, return it directly
            if isinstance(response, list):
                return response

            # If response is a dict with 'data' key
            if isinstance(response, dict):
                data = response.get('data')
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get('orders', [])

            return []

        except Exception as e:
            self._log_error("Failed to get open orders", e)
            return []

    def get_positions(self) -> list[dict]:
        """
        Get all open positions.

        Returns:
            List of open positions
        """
        try:
            client = self._get_client()
            account = client.get_account_v3()

            if account and 'data' in account:
                return account['data'].get('openPositions', [])

            return []

        except Exception as e:
            self._log_error("Failed to get positions", e)
            return []

    def get_trade_fills(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """
        Get trade fill history.

        Args:
            symbol: Optional symbol filter
            limit: Maximum number of fills to return

        Returns:
            List of trade fills
        """
        try:
            client = self._get_client()

            params = {"limit": limit}
            if symbol:
                params['symbol'] = symbol

            response = client.fills_v3(**params)

            if response and 'data' in response:
                return response['data'].get('fills', [])

            return []

        except Exception as e:
            self._log_error("Failed to get trade fills", e)
            return []


class MockApexOmniClient(ApexOmniClient):
    """
    Mock client for dry-run mode and testing.

    Simulates API responses without making real API calls.
    """

    # Realistic mock prices per symbol
    MOCK_PRICES = {
        "BTC-USDT": Decimal("95000.0"),
        "ETH-USDT": Decimal("3500.0"),
        "DOGE-USDT": Decimal("0.14"),
        "1000PEPE-USDT": Decimal("0.004"),  # Low-value token for small accounts
        "SOL-USDT": Decimal("180.0"),
        "XRP-USDT": Decimal("2.20"),
        "LINEA-USDT": Decimal("0.0093"),  # Cheapest tradeable symbol
        "ARB-USDT": Decimal("0.20"),
        "SUNDOG-USDT": Decimal("0.011"),
    }

    def __init__(self, config: APIConfig):
        super().__init__(config)
        self._mock_balance = AccountBalance(
            total_equity=Decimal("1000.0"),
            available_balance=Decimal("950.0"),
            margin_balance=Decimal("1000.0"),
            unrealized_pnl=Decimal("0")
        )
        self._mock_price = Decimal("95000.0")  # Default BTC price (for backward compat)
        self._order_counter = 0

    def test_connection(self) -> bool:
        self.logger.info("[DRY-RUN] Mock API connection test successful")
        return True

    def get_account_balance(self) -> Optional[AccountBalance]:
        self.logger.info("[DRY-RUN] Returning mock account balance")
        return self._mock_balance

    def get_current_price(self, symbol: str) -> Optional[Decimal]:
        self.logger.info(f"[DRY-RUN] Returning mock price for {symbol}")
        # Return symbol-specific price, or default to BTC price
        return self.MOCK_PRICES.get(symbol, self._mock_price)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        size: Decimal,
        price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False
    ) -> OrderResult:
        self._order_counter += 1
        mock_order_id = f"MOCK-{self._order_counter:06d}"

        if price is None:
            price = self._mock_price

        self.logger.info(
            f"[DRY-RUN] Would place {order_type} {side} order: "
            f"{size} {symbol} @ {price}"
        )

        return OrderResult(
            success=True,
            order_id=mock_order_id,
            client_order_id=client_order_id or f"client-{mock_order_id}",
            symbol=symbol,
            side=side.upper(),
            order_type=order_type.upper(),
            size=size,
            price=price,
            filled_size=size,
            filled_price=price,
            status="FILLED",
            fee=size * price * Decimal("0.0005"),  # 0.05% fee
            timestamp=int(time.time() * 1000)
        )

    def get_symbol_config(self, symbol: str) -> Optional[SymbolConfig]:
        return SymbolConfig(
            symbol=symbol,
            base_currency=symbol.split("-")[0],
            quote_currency=symbol.split("-")[1] if "-" in symbol else "USDT",
            min_order_size=Decimal("0.001"),
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            max_leverage=100,
            enable_open_position=True,
            enable_trade=True,
        )

    def get_all_symbols(self, tradeable_only: bool = True) -> list[SymbolConfig]:
        """Return mock list of available symbols with realistic configurations."""
        mock_symbols = [
            SymbolConfig(
                symbol="LINEA-USDT",
                base_currency="LINEA",
                quote_currency="USDT",
                min_order_size=Decimal("1"),  # ~$0.01 min order (cheapest!)
                tick_size=Decimal("0.0001"),
                step_size=Decimal("1"),
                max_leverage=50,
                enable_open_position=True,
                enable_trade=True,
            ),
            SymbolConfig(
                symbol="BTC-USDT",
                base_currency="BTC",
                quote_currency="USDT",
                min_order_size=Decimal("0.001"),  # ~$95 min order
                tick_size=Decimal("0.1"),
                step_size=Decimal("0.001"),
                max_leverage=100,
                enable_open_position=True,
                enable_trade=True,
            ),
            SymbolConfig(
                symbol="ETH-USDT",
                base_currency="ETH",
                quote_currency="USDT",
                min_order_size=Decimal("0.01"),  # ~$35 min order
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.01"),
                max_leverage=100,
                enable_open_position=True,
                enable_trade=True,
            ),
            SymbolConfig(
                symbol="DOGE-USDT",
                base_currency="DOGE",
                quote_currency="USDT",
                min_order_size=Decimal("1"),  # ~$0.14 min order
                tick_size=Decimal("0.00001"),
                step_size=Decimal("1"),
                max_leverage=50,
                enable_open_position=True,
                enable_trade=True,
            ),
            SymbolConfig(
                symbol="ARB-USDT",
                base_currency="ARB",
                quote_currency="USDT",
                min_order_size=Decimal("0.1"),  # ~$0.02 min order
                tick_size=Decimal("0.0001"),
                step_size=Decimal("0.1"),
                max_leverage=50,
                enable_open_position=True,
                enable_trade=True,
            ),
        ]
        self.logger.info(f"[DRY-RUN] Returning {len(mock_symbols)} mock symbols")
        return mock_symbols

    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        return []

    def get_positions(self) -> list[dict]:
        return []


def create_client(config: APIConfig, dry_run: bool = False) -> ApexOmniClient:
    """
    Factory function to create the appropriate client.

    Args:
        config: API configuration
        dry_run: Whether to use mock client

    Returns:
        ApexOmniClient or MockApexOmniClient
    """
    if dry_run:
        return MockApexOmniClient(config)
    return ApexOmniClient(config)
