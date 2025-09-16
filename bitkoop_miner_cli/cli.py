#!/usr/bin/env python3
"""bitkoop CLI - Command-line interface for bitkoop mining operations"""

import argparse
import sys
from typing import Callable

from bittensor_wallet import Wallet

from bitkoop_miner_cli.commands import (
    delete_code_command,
    rank_command,
    recheck,
    sites,
    submit_code_command,
    view_codes,
)

# view_product_categories,  # DISABLED: Shopify integration provides this
from bitkoop_miner_cli.utils.display import (
    handle_connection_error,
    handle_site_not_found_error,
    handle_unexpected_error,
    handle_validation_error,
    print_warning,
)
from bitkoop_miner_cli.utils.network import init_network_from_args, set_network


class CommandRegistry:
    """Registry for CLI commands with their configurations"""

    def __init__(self):
        self.commands: dict[str, dict] = {}

    def register(
        self, name: str, help_text: str, func: Callable, needs_wallet: bool = False
    ):
        """Register a command with its configuration"""
        self.commands[name] = {
            "help": help_text,
            "func": func,
            "needs_wallet": needs_wallet,
        }
        return self

    def add_to_parser(self, subparsers):
        """Add all registered commands to the argument parser"""
        for name, config in self.commands.items():
            parser = subparsers.add_parser(name, help=config["help"])
            config["parser"] = parser
            parser.set_defaults(func=config["func"])
            if config["needs_wallet"]:
                Wallet.add_args(parser)
                        # Accept network flag after the subcommand as well
            parser.add_argument(
                "--subtensor.network",
                dest="subtensor.network",
                choices=["finney", "test"],
                help="Select network (finney/test)",
            )


def setup_submit_code(parser):
    """Configure submit-code command arguments"""
    parser.add_argument("site", help="Site to submit code for")
    parser.add_argument(
        "code",
        help="Coupon code (letters, numbers, hyphens and dashes - no spaces or underscores)",
    )

    # DISABLED FIELDS - Shopify integration provides these
    # parser.add_argument("--expires-at", help="Expiration date (YYYY-MM-DD)")
    # parser.add_argument("--category", help="Category ID (integer) or description")
    # parser.add_argument("--restrictions", help="Restrictions or terms (max 1000 chars)")
    # parser.add_argument("--country-code", help="Country code (e.g., 'US', 'CA')")
    # parser.add_argument("--product-url", help="Product URL where coupon was used")
    # parser.add_argument(
    #     "--global",
    #     dest="is_global",
    #     action="store_true",
    #     help="Mark coupon as globally applicable",
    # )
    # parser.set_defaults(is_global=None)

    parser.epilog = """
Examples:
bitkoop submit-code amazon.com SAVE20
bitkoop submit-code target.com HOLIDAY-2025
bitkoop submit-code target.com SAVE20 --wallet.name my_wallet_name --wallet.hotkey my_wallet_hotkey
"""
    parser.formatter_class = argparse.RawDescriptionHelpFormatter


def setup_view_codes(parser):
    """Configure view-codes command arguments"""
    parser.add_argument(
        "site",
        nargs="?",
        default="all",
        help="Site to view codes for (or 'all' for all sites)",
    )
    # DISABLED: Category filtering - Shopify integration handles this
    # parser.add_argument("--category", help="Filter by category name (partial match)")
    parser.add_argument(
        "--limit", type=int, default=100, help="Codes per page (default: 100)"
    )
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--offset", type=int, default=0, help="Legacy: Skip N codes")
    parser.epilog = """
Examples:
bitkoop view-codes                    # View all valid coupons
bitkoop view-codes amazon.com         # View coupons for a specific site
bitkoop view-codes --page 2 --limit 20
bitkoop view-codes --wallet.name my_wallet
"""
    parser.formatter_class = argparse.RawDescriptionHelpFormatter


def setup_list_sites(parser):
    """Configure list-sites command arguments"""
    parser.add_argument("--domain", help="Filter by domain (partial match)")
    parser.add_argument("--site-id", type=int, help="Filter by site ID")
    parser.add_argument("--page", type=int, default=1, help="Page number")
    parser.add_argument("--limit", type=int, default=100, help="Sites per page")
    parser.add_argument(
        "--sort-by",
        choices=["store_id", "store_domain", "store_status", "miner_hotkey"],
        default="store_status",
        help="Sort field",
    )
    parser.add_argument("--sort-order", choices=["asc", "desc"], help="Sort direction")
    parser.add_argument("--all", action="store_true", help="Fetch all sites")
    parser.epilog = """
Examples:
bitkoop list-sites --limit 5
bitkoop list-sites --domain amazon
bitkoop list-sites --sort-by store_domain
"""
    parser.formatter_class = argparse.RawDescriptionHelpFormatter


# DISABLED: List categories command - Shopify integration provides this
# def setup_list_categories(parser):
#     """Configure list-categories command arguments"""
#     parser.add_argument("--name", help="Filter by name (partial match)")
#     parser.add_argument("--page", type=int, default=1, help="Page number")
#     parser.add_argument("--limit", type=int, default=100, help="Categories per page")
#     parser.add_argument(
#         "--sort-by",
#         choices=["category_id", "category_name"],
#         default="category_id",
#         help="Sort field",
#     )
#     parser.add_argument(
#         "--sort-order", choices=["asc", "desc"], default="asc", help="Sort direction"
#     )
#     parser.epilog = """
# Examples:
# bitkoop list-categories --name electro
# bitkoop list-categories --limit 10 --page 2
# """
#     parser.formatter_class = argparse.RawDescriptionHelpFormatter


def setup_rank(parser):
    """Configure rank command arguments"""
    parser.epilog = """
Examples:
bitkoop rank --wallet.name mywallet --wallet.hotkey myhotkey   # View rank for wallet and hotkey
"""
    parser.formatter_class = argparse.RawDescriptionHelpFormatter


def setup_simple_code_command(parser, action: str):
    """Configure delete-code and recheck-code commands"""
    parser.add_argument("site", help=f"Site to {action} code for")
    parser.add_argument("code", help=f"Coupon code to {action}")


def create_parser():
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(description="BitKoop Mining CLI")
    # Global network argument support
    parser.add_argument(
        "--subtensor.network",
        dest="subtensor.network",
        choices=["finney", "test"],
        help="Select network (finney/test)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    registry = CommandRegistry()
    registry.register(
        "submit-code",
        "Submit a new coupon code",
        submit_code_command.submit_code_command,
        needs_wallet=True,
    )
    registry.register(
        "view-codes",
        "View coupon codes",
        view_codes.view_codes_command,
        needs_wallet=True,
    )
    registry.register(
        "list-sites", "List all available sites", sites.list_sites_command
    )
    # DISABLED: List categories command - Shopify integration provides this
    # registry.register(
    #     "list-categories",
    #     "List all product categories",
    #     view_product_categories.list_categories_command,
    # )
    registry.register(
        "rank",
        "List miner rankings by points",
        rank_command.list_rank_command,
        needs_wallet=True,
    )
    registry.register(
        "delete-code",
        "Delete a coupon code",
        delete_code_command.delete_code_command,
        needs_wallet=True,
    )
    registry.register(
        "recheck-code",
        "Recheck a coupon code across all validators",
        recheck.recheck_code_command,
        needs_wallet=True,
    )

    registry.add_to_parser(subparsers)

    setup_submit_code(registry.commands["submit-code"]["parser"])
    setup_view_codes(registry.commands["view-codes"]["parser"])
    setup_list_sites(registry.commands["list-sites"]["parser"])
    # DISABLED: setup_list_categories(registry.commands["list-categories"]["parser"])
    setup_rank(registry.commands["rank"]["parser"])
    setup_simple_code_command(registry.commands["delete-code"]["parser"], "delete")
    setup_simple_code_command(registry.commands["recheck-code"]["parser"], "recheck")

    return parser


def handle_error(error: Exception) -> int:
    """Centralized error handling"""
    error_msg = str(error)

    if isinstance(error, ValueError):
        if "not found in supervisor" in error_msg:
            site = error_msg.split("'")[1] if "'" in error_msg else "unknown"
            handle_site_not_found_error(site)
        else:
            handle_validation_error(error_msg)
        return 1

    if isinstance(error, RuntimeError):
        handle_connection_error(error_msg)
        return 1

    if isinstance(error, KeyboardInterrupt):
        print_warning("Operation cancelled by user")
        return 0

    handle_unexpected_error(error_msg)
    return 1


def main():
    """Main entry point for the CLI"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        # Initialize global network selection from args before executing command
        init_network_from_args(args)
        args.func(args)
    except Exception as e:
        sys.exit(handle_error(e))


if __name__ == "__main__":
    main()
