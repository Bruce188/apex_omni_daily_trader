#!/usr/bin/env python3
"""
ApexOmni Account Debug Script

Investigates the account state to diagnose "insufficient margin" errors.
Checks for:
1. Open positions consuming margin
2. Open orders reserving margin
3. Available vs used margin
4. Attempts a minimal order with full response capture

KEY FINDINGS FROM DEBUGGING (2025-11-22):
=========================================
1. SDK INITIALIZATION: The ApexOmni SDK requires BOTH configs_v3() AND
   get_account_v3() to be called BEFORE placing orders. These populate
   self.configV3 and self.accountV3 which are required for order signing.

2. SYMBOL TRADABILITY: Many symbols have enableOpenPosition=false which means
   new positions cannot be opened. Always check this flag when selecting symbols.
   The cheapest tradeable symbol at time of writing is LINEA-USDT (~$0.009/unit).

3. RESPONSE PARSING: Successful order responses have 'data' with 'id' field,
   NOT a 'code' field. Error responses have a 'code' field with non-zero value.

4. EMPTY STRING HANDLING: Some response fields like 'averagePrice' and 'fee'
   may be empty strings. parse_decimal() must handle these gracefully.

Usage:
    python scripts/debug_account.py
"""

import os
import sys
import json
import time
from pathlib import Path
from decimal import Decimal

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

# Load environment
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


def get_client():
    """Create the API client."""
    from apexomni.http_private_sign import HttpPrivateSign

    # Get network settings
    network = os.getenv("APEX_NETWORK", "testnet")

    if network == "mainnet":
        from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_MAIN
        endpoint = APEX_OMNI_HTTP_MAIN
        network_id = NETWORKID_MAIN
    else:
        from apexomni.constants import APEX_OMNI_HTTP_TEST, NETWORKID_TEST
        endpoint = APEX_OMNI_HTTP_TEST
        network_id = NETWORKID_TEST

    print(f"\n{'='*60}")
    print(f"NETWORK: {network}")
    print(f"ENDPOINT: {endpoint}")
    print(f"NETWORK_ID: {network_id}")
    print(f"{'='*60}")

    # Get credentials
    api_key = os.getenv("APEX_API_KEY", "")
    api_secret = os.getenv("APEX_API_SECRET", "")
    passphrase = os.getenv("APEX_PASSPHRASE", "")
    zk_seeds = os.getenv("APEX_ZK_SEEDS", "")
    zk_l2key = os.getenv("APEX_ZK_L2KEY", "")

    if not all([api_key, api_secret, passphrase, zk_seeds]):
        print("ERROR: Missing required credentials in .env file")
        print(f"  API_KEY: {'set' if api_key else 'MISSING'}")
        print(f"  API_SECRET: {'set' if api_secret else 'MISSING'}")
        print(f"  PASSPHRASE: {'set' if passphrase else 'MISSING'}")
        print(f"  ZK_SEEDS: {'set' if zk_seeds else 'MISSING'}")
        print(f"  ZK_L2KEY: {'set' if zk_l2key else 'optional'}")
        sys.exit(1)

    client = HttpPrivateSign(
        endpoint,
        network_id=network_id,
        zk_seeds=zk_seeds,
        zk_l2Key=zk_l2key or '',
        api_key_credentials={
            'key': api_key,
            'secret': api_secret,
            'passphrase': passphrase
        }
    )

    return client


def format_json(data):
    """Format data as pretty JSON."""
    return json.dumps(data, indent=2, default=str)


def get_account_info(client):
    """Get full account information."""
    print("\n" + "="*60)
    print("ACCOUNT INFORMATION")
    print("="*60)

    try:
        account = client.get_account_v3()
        print("\nFull account response:")
        print(format_json(account))

        # Parse key fields
        if account:
            print("\n--- Parsed Account Data ---")

            # Contract wallets (USDT balance)
            contract_wallets = account.get('contractWallets', [])
            print(f"\nContract Wallets ({len(contract_wallets)}):")
            for wallet in contract_wallets:
                print(f"  {wallet.get('token', 'UNKNOWN')}: {wallet.get('balance', '0')}")

            # Positions
            positions = account.get('positions', [])
            print(f"\nPositions ({len(positions)}):")
            if positions:
                for pos in positions:
                    print(f"  Symbol: {pos.get('symbol', 'UNKNOWN')}")
                    print(f"    Size: {pos.get('size', '0')}")
                    print(f"    Side: {pos.get('side', 'UNKNOWN')}")
                    print(f"    Entry Price: {pos.get('entryPrice', '0')}")
                    print(f"    Mark Price: {pos.get('markPrice', '0')}")
                    print(f"    Unrealized PnL: {pos.get('unrealizedPnl', '0')}")
                    print(f"    Margin: {pos.get('initialMargin', '0')}")
                    print(f"    Leverage: {pos.get('leverage', '1')}")
            else:
                print("  (No open positions)")

            # Open orders in account
            open_orders = account.get('openOrders', [])
            print(f"\nOpen Orders in Account ({len(open_orders)}):")
            if open_orders:
                for order in open_orders:
                    print(f"  {format_json(order)}")
            else:
                print("  (No open orders)")

            # Account details
            print(f"\nAccount Details:")
            print(f"  Total Equity: {account.get('totalEquity', 'N/A')}")
            print(f"  Available Balance: {account.get('availableBalance', 'N/A')}")
            print(f"  Initial Margin: {account.get('initialMargin', 'N/A')}")
            print(f"  Maintenance Margin: {account.get('maintenanceMargin', 'N/A')}")
            print(f"  Account Leverage: {account.get('leverage', 'N/A')}")
            print(f"  Margin Type: {account.get('marginType', 'N/A')}")

        return account
    except Exception as e:
        print(f"ERROR getting account info: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_open_orders(client):
    """Get all open orders."""
    print("\n" + "="*60)
    print("OPEN ORDERS")
    print("="*60)

    try:
        orders = client.open_orders_v3()
        print("\nOpen orders response:")
        print(format_json(orders))

        # Parse orders
        if orders:
            if isinstance(orders, list):
                order_list = orders
            elif isinstance(orders, dict):
                order_list = orders.get('data', orders.get('orders', []))
                if isinstance(order_list, dict):
                    order_list = order_list.get('orders', [])
            else:
                order_list = []

            print(f"\nParsed Orders ({len(order_list)}):")
            if order_list:
                for order in order_list:
                    print(f"  ID: {order.get('id', 'UNKNOWN')}")
                    print(f"    Symbol: {order.get('symbol', 'UNKNOWN')}")
                    print(f"    Side: {order.get('side', 'UNKNOWN')}")
                    print(f"    Type: {order.get('type', 'UNKNOWN')}")
                    print(f"    Size: {order.get('size', '0')}")
                    print(f"    Price: {order.get('price', '0')}")
                    print(f"    Status: {order.get('status', 'UNKNOWN')}")
                    print()
            else:
                print("  (No open orders)")

        return orders
    except Exception as e:
        print(f"ERROR getting open orders: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_configs(client):
    """Get exchange configs to find tradeable symbols."""
    print("\n" + "="*60)
    print("EXCHANGE CONFIGURATION (Symbol Info)")
    print("="*60)

    try:
        configs = client.configs_v3()

        # Find cheapest symbol
        contract_config = configs.get('data', {}).get('contractConfig', {})
        perpetuals = contract_config.get('perpetualContract', [])

        print(f"\nFound {len(perpetuals)} perpetual contracts")
        print("\nLow-value symbols (min order < 100 units):")

        for contract in perpetuals:
            min_order = float(contract.get('minOrderSize', '0'))
            symbol = contract.get('symbol', 'UNKNOWN')
            if min_order < 100:
                print(f"  {symbol}: min={min_order}, tick={contract.get('tickSize', '?')}, step={contract.get('stepSize', '?')}")

        return configs
    except Exception as e:
        print(f"ERROR getting configs: {e}")
        return None


def get_current_price(symbol="1000PEPE-USDT"):
    """Get current price for a symbol."""
    from apexomni.http_public import HttpPublic

    network = os.getenv("APEX_NETWORK", "testnet")
    if network == "mainnet":
        from apexomni.constants import APEX_OMNI_HTTP_MAIN
        endpoint = APEX_OMNI_HTTP_MAIN
    else:
        from apexomni.constants import APEX_OMNI_HTTP_TEST
        endpoint = APEX_OMNI_HTTP_TEST

    public_client = HttpPublic(endpoint)
    ticker = public_client.ticker_v3(symbol=symbol)

    if ticker and 'data' in ticker:
        data = ticker['data']
        if isinstance(data, list) and len(data) > 0:
            return float(data[0].get('lastPrice', '0'))
        elif isinstance(data, dict):
            return float(data.get('lastPrice', '0'))

    return None


def test_minimal_order(client):
    """Attempt to place a minimal order and capture full response."""
    print("\n" + "="*60)
    print("TEST MINIMAL ORDER")
    print("="*60)

    # Use 1000PEPE-USDT - typically cheapest
    symbol = "1000PEPE-USDT"

    # Get current price
    current_price = get_current_price(symbol)
    print(f"\n{symbol} current price: {current_price}")

    if current_price is None:
        print("ERROR: Could not get current price")
        return None

    # Minimum order size for 1000PEPE-USDT is typically 1
    size = "1"  # Try absolute minimum

    order_value = float(size) * current_price
    print(f"Order value: ${order_value:.6f} USDT")

    # Prepare order params
    order_params = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "size": size,
        "price": str(current_price),
        "timestampSeconds": int(time.time()),
    }

    print(f"\nOrder parameters:")
    print(format_json(order_params))

    print("\nAttempting to place order...")

    try:
        response = client.create_order_v3(**order_params)
        print(f"\nFULL API RESPONSE:")
        print(format_json(response))

        if response:
            if response.get('code') == '0':
                print("\n*** ORDER SUCCESSFUL ***")
                data = response.get('data', {})
                print(f"Order ID: {data.get('id', 'UNKNOWN')}")

                # Immediately close the position
                print("\nClosing position...")
                close_params = {
                    "symbol": symbol,
                    "side": "SELL",
                    "type": "MARKET",
                    "size": size,
                    "price": str(current_price),
                    "timestampSeconds": int(time.time()),
                    "reduceOnly": True,
                }
                close_response = client.create_order_v3(**close_params)
                print(f"Close response:")
                print(format_json(close_response))
            else:
                print(f"\n*** ORDER FAILED ***")
                print(f"Error code: {response.get('code')}")
                print(f"Error message: {response.get('message', response.get('msg', 'Unknown'))}")

                # Additional error details
                if 'data' in response:
                    print(f"Error data: {format_json(response.get('data'))}")

        return response
    except Exception as e:
        print(f"EXCEPTION during order: {e}")
        import traceback
        traceback.print_exc()
        return None


def cancel_all_open_orders(client):
    """Cancel all open orders."""
    print("\n" + "="*60)
    print("CANCELLING ALL OPEN ORDERS")
    print("="*60)

    try:
        orders = client.open_orders_v3()

        # Parse orders
        if orders:
            if isinstance(orders, list):
                order_list = orders
            elif isinstance(orders, dict):
                order_list = orders.get('data', orders.get('orders', []))
                if isinstance(order_list, dict):
                    order_list = order_list.get('orders', [])
            else:
                order_list = []
        else:
            order_list = []

        if not order_list:
            print("No open orders to cancel")
            return

        print(f"Found {len(order_list)} open orders to cancel")

        for order in order_list:
            order_id = order.get('id')
            if order_id:
                print(f"  Cancelling order {order_id}...")
                try:
                    result = client.delete_order_v3(id=order_id)
                    print(f"    Result: {format_json(result)}")
                except Exception as e:
                    print(f"    Error: {e}")

    except Exception as e:
        print(f"ERROR cancelling orders: {e}")


def close_all_positions(client):
    """Close all open positions."""
    print("\n" + "="*60)
    print("CLOSING ALL OPEN POSITIONS")
    print("="*60)

    try:
        account = client.get_account_v3()
        if not account:
            print("Could not get account")
            return

        positions = account.get('positions', [])

        if not positions:
            print("No open positions to close")
            return

        print(f"Found {len(positions)} open positions to close")

        for pos in positions:
            symbol = pos.get('symbol')
            size = pos.get('size', '0')
            side = pos.get('side', '')

            if float(size) == 0:
                continue

            # Opposite side to close
            close_side = "SELL" if side == "LONG" else "BUY"

            print(f"\n  Closing {symbol}: {side} {size}")

            # Get current price
            price = get_current_price(symbol)
            if price is None:
                print(f"    Could not get price for {symbol}")
                continue

            close_params = {
                "symbol": symbol,
                "side": close_side,
                "type": "MARKET",
                "size": str(abs(float(size))),
                "price": str(price),
                "timestampSeconds": int(time.time()),
                "reduceOnly": True,
            }

            try:
                result = client.create_order_v3(**close_params)
                print(f"    Close result: {format_json(result)}")
            except Exception as e:
                print(f"    Error closing: {e}")

    except Exception as e:
        print(f"ERROR closing positions: {e}")


def main():
    """Main entry point."""
    print("="*60)
    print("APEXOMNI ACCOUNT DEBUG SCRIPT")
    print("="*60)

    # Create client
    client = get_client()

    # Get account info
    account = get_account_info(client)

    # Get open orders
    orders = get_open_orders(client)

    # Check if there are orders/positions to clean up
    has_positions = False
    has_orders = False

    if account:
        positions = account.get('positions', [])
        for pos in positions:
            if float(pos.get('size', '0')) != 0:
                has_positions = True
                break

    if orders:
        if isinstance(orders, list) and orders:
            has_orders = True
        elif isinstance(orders, dict):
            order_list = orders.get('data', orders.get('orders', []))
            if isinstance(order_list, dict):
                order_list = order_list.get('orders', [])
            if order_list:
                has_orders = True

    # Ask user if they want to clean up
    if has_positions or has_orders:
        print("\n" + "="*60)
        print("CLEANUP OPTIONS")
        print("="*60)

        if has_positions:
            print("  - Found open positions that may be consuming margin")
        if has_orders:
            print("  - Found open orders that may be reserving margin")

        print("\nWould you like to:")
        print("  1. Cancel all open orders")
        print("  2. Close all open positions")
        print("  3. Both (cancel orders and close positions)")
        print("  4. Skip cleanup and test order")
        print("  5. Exit")

        choice = input("\nEnter choice (1-5): ").strip()

        if choice == "1":
            cancel_all_open_orders(client)
        elif choice == "2":
            close_all_positions(client)
        elif choice == "3":
            cancel_all_open_orders(client)
            time.sleep(1)
            close_all_positions(client)
        elif choice == "5":
            print("Exiting...")
            return

    # Get configs for reference
    get_configs(client)

    # Test minimal order
    print("\n" + "="*60)
    print("READY TO TEST ORDER")
    print("="*60)

    proceed = input("\nProceed with test order? (y/n): ").strip().lower()
    if proceed == 'y':
        test_minimal_order(client)
    else:
        print("Skipping test order")

    # Final account state
    print("\n" + "="*60)
    print("FINAL ACCOUNT STATE")
    print("="*60)
    get_account_info(client)

    print("\n" + "="*60)
    print("DEBUG COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
