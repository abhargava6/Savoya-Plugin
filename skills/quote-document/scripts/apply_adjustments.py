#!/usr/bin/env python3
"""Legacy fail-safe: local monetary mutations are no longer supported.

Use calculate_temporary_quote_units and replace raw_quote.json instead.  Calling
this command without mutation flags is harmless and leaves the file unchanged.
"""

import argparse, json, sys


def recompute(quote):
    """Compatibility shim for old callers; intentionally performs no arithmetic."""
    return quote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("quote")
    parser.add_argument("--add", action="append", default=[])
    parser.add_argument("--remove", action="append", default=[])
    parser.add_argument("--waive", action="append", default=[])
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    if args.add or args.remove or args.waive or args.clear:
        sys.exit(
            "Local price changes are disabled. Re-quote through Savoya MCP so Core remains authoritative."
        )
    with open(args.quote, encoding="utf-8") as handle:
        quote = json.load(handle)
    print(f"No changes made. Core total: ${(quote.get('total_cents') or 0) / 100:,.2f}")


if __name__ == "__main__":
    main()
