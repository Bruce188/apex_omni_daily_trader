#!/bin/bash
set -e

echo "=========================================="
echo "ApexOmni Daily Trader Container"
echo "=========================================="
echo ""
echo "Trading Rules:"
echo "  - 1 trade per day maximum"
echo "  - +0.1 bonus per day traded"
echo "  - +0.5 maximum per week (5 days)"
echo ""
echo "Starting trader..."
echo ""

exec python3 trader.py
