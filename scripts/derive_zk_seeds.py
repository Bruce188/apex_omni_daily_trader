#!/usr/bin/env python3
"""
Derive ZK Seeds from Ethereum Private Key

This script derives the ZK seeds needed for signing ApexOmni trades.
The ZK seeds are derived from your Ethereum wallet signature.

SECURITY WARNING:
- Your Ethereum private key is sensitive! Never share it.
- This script does NOT store your private key anywhere.
- The derived seeds are saved to .env file for trading.

Usage:
  python3 derive_zk_seeds.py

Then enter your Ethereum private key when prompted.
"""

import os
import sys
from getpass import getpass
from textwrap import dedent

def derive_zk_keys(eth_private_key=None):
    print(dedent("""
        ============================================================
        APEXOMNI ZK SEEDS DERIVATION
        ============================================================
    """).strip())
    print()

    # Get private key from argument, env var, or prompt
    if not eth_private_key:
        eth_private_key = os.environ.get('ETH_PRIVATE_KEY', '')

    if not eth_private_key:
        print(dedent("""
            This will derive ZK seeds from your Ethereum private key.
            The private key is NOT stored - only the derived seeds are saved.

            Enter your Ethereum private key:
            (This is the private key for wallet <YOUR_WALLET_ADDRESS>)
        """).strip())
        print()
        try:
            eth_private_key = getpass("Private Key: ").strip()
        except EOFError:
            print(dedent("""
                ERROR: Cannot read input. Pass key as argument or set ETH_PRIVATE_KEY env var
                Usage: python3 derive_zk_seeds.py YOUR_PRIVATE_KEY
            """).strip())
            return False

    if not eth_private_key:
        print("ERROR: No private key provided")
        return False

    # Remove 0x prefix if present
    if eth_private_key.startswith('0x'):
        eth_private_key = eth_private_key[2:]

    # Validate length (64 hex characters = 32 bytes)
    if len(eth_private_key) != 64:
        print(f"ERROR: Invalid private key length ({len(eth_private_key)} chars, expected 64)")
        return False

    print()
    print("Deriving ZK keys...")

    try:
        from apexomni.http_private_v3 import HttpPrivate_v3
        from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_MAIN

        # Initialize client with Ethereum private key
        print(f"Connecting to {APEX_OMNI_HTTP_MAIN}...")
        client = HttpPrivate_v3(
            APEX_OMNI_HTTP_MAIN,
            network_id=NETWORKID_MAIN,
            eth_private_key=eth_private_key
        )

        print(f"Wallet address: {client.default_address}")

        # Load configs (required before derivation)
        print("Loading configuration...")
        try:
            configs = client.configs_v3()
            print("Configuration loaded successfully")
        except Exception as e:
            print(f"Warning: Could not load configs - {e}")
            print("Continuing anyway...")

        # Derive ZK keys
        print("Deriving ZK keys from wallet signature...")
        zk_keys = client.derive_zk_key(client.default_address)

        if not zk_keys:
            print("ERROR: Failed to derive ZK keys")
            return False

        seeds = zk_keys.get('seeds', '')
        l2_key = zk_keys.get('l2Key', '')
        pub_key_hash = zk_keys.get('pubKeyHash', '')

        seeds_display = f"{seeds[:20]}...{seeds[-10:]}" if len(seeds) > 30 else seeds
        l2key_display = f"{l2_key[:20]}...{l2_key[-10:]}" if len(l2_key) > 30 else l2_key

        print(dedent(f"""

            ============================================================
            ZK KEYS DERIVED SUCCESSFULLY!
            ============================================================

            Seeds:       {seeds_display}
            L2 Key:      {l2key_display}
            PubKeyHash:  {pub_key_hash}
        """).strip())
        print()

        # Update .env file
        env_path = os.path.join(os.path.dirname(__file__), '.env')

        # Read existing .env
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()

        # Update or add ZK seeds
        lines = env_content.split('\n')
        new_lines = []
        seeds_set = False
        l2key_set = False

        for line in lines:
            if line.startswith('APEX_ZK_SEEDS='):
                new_lines.append(f'APEX_ZK_SEEDS={seeds}')
                seeds_set = True
            elif line.startswith('APEX_ZK_L2KEY='):
                new_lines.append(f'APEX_ZK_L2KEY={l2_key}')
                l2key_set = True
            else:
                new_lines.append(line)

        if not seeds_set:
            # Find the right place to insert (after passphrase)
            for i, line in enumerate(new_lines):
                if line.startswith('APEX_PASSPHRASE='):
                    new_lines.insert(i + 1, f'APEX_ZK_SEEDS={seeds}')
                    new_lines.insert(i + 2, f'APEX_ZK_L2KEY={l2_key}')
                    seeds_set = True
                    l2key_set = True
                    break

        # Write updated .env
        with open(env_path, 'w') as f:
            f.write('\n'.join(new_lines))

        print("ZK Seeds saved to .env file!")
        print()
        print("You can now run: python3 execute_trades.py")

        return True

    except ImportError as e:
        print(f"ERROR: Missing dependency - {e}")
        print("Install with: pip install apexomni")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    # Accept private key as command line argument
    private_key = sys.argv[1] if len(sys.argv) > 1 else None
    success = derive_zk_keys(private_key)
    sys.exit(0 if success else 1)
