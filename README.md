# BitKoop Miner CLI

A command-line interface for BitKoop mining operations on the Bittensor network.

## Overview

BitKoop Miner CLI provides a comprehensive set of commands for managing coupon codes, sites, categories, and monitoring your mining performance on the BitKoop network.

## Available Commands

The CLI offers the following commands:

- **submit-code** - Submit a new coupon code
- **view-codes** - View coupon codes (all valid codes by default, or your own codes with wallet authentication)
- **list-sites** - List all available sites
- **list-categories** - List all available product categories
- **delete-code** - Delete a coupon code
- **recheck-code** - Recheck a coupon code across ALL validators in the network
- **rank** - Displays the miner's leaderboard position, total points, and a summary of submitted coupons.
 

## Installation

### From GitHub (recommended)
```bash
pip install git+https://github.com/BitKoopLabs/BitKoop-CLI.git@x.y.z
```

## Usage

After installation, you can use the `bitkoop` command:

```bash
bitkoop --help
```

## Command Reference

### Submit Code
Submit a new coupon code to the network.

```bash
bitkoop submit-code <site> <code> [options]
```

**Options:**
- `--expires-at` - Expiration date (YYYY-MM-DD)
- `--category` - Category ID (integer) or description
- `--restrictions` - Restrictions or terms (max 1000 chars)
- `--country-code` - Country code (e.g., 'US', 'CA')
- `--product-url` - Product URL where coupon was used
- `--global` - Mark coupon as globally applicable

**Example:**
```bash
bitkoop submit-code amazon.com WELCOME10 --category "electronics"
```

### View Codes
View coupon codes - all valid codes by default, or your own codes with wallet authentication.

```bash
bitkoop view-codes [site] [options]
```

**Arguments:**
- `site` - Site to view codes for (or 'all' for all sites, default: 'all')

**Options:**
- `--category` - Filter coupons by category name (partial, case-insensitive match)
- `--limit` - Maximum number of codes to display per page (default: 100)
- `--page` - Page number for pagination (default: 1)
- `--offset` - Legacy: Number of codes to skip for pagination (default: 0)
- `--wallet.name` - Wallet name for authentication
- `--wallet.hotkey` - Wallet hotkey for authentication
- `--wallet.path` - Wallet path for authentication

**Examples:**
```bash
bitkoop view-codes                              # View all valid coupons
bitkoop view-codes amazon.com                   # View coupons for a specific site
bitkoop view-codes --category electronics       # View coupons in the 'electronics' category
bitkoop view-codes --page 2 --limit 20          # View second page of results (20 per page)
bitkoop view-codes --wallet.name my_wallet --wallet.hotkey my_hotkey  # View your own submitted coupons
```

### List Sites
List all available sites with filtering and pagination options.

```bash
bitkoop list-sites [options]
```

**Options:**
- `--domain` - Filter by domain name (partial match, e.g., 'amazon' for amazon.com)
- `--site-id` - Filter by specific site ID
- `--page` - Page number for pagination (default: 1)
- `--limit` - Number of sites per page (default: 100)
- `--sort-by` - Field to sort by: store_id, store_domain, store_status, miner_hotkey (default: store_status)
- `--sort-order` - Sort direction: asc, desc (default: desc for status, asc for others)
- `--all` - Fetch all sites (ignore pagination)

**Examples:**
```bash
bitkoop list-sites                              # List all sites (sorted by status)
bitkoop list-sites --limit 5                    # Show first 5 sites
bitkoop list-sites --limit 5 --page 2           # Show sites 6-10
bitkoop list-sites --domain amazon              # Find sites containing 'amazon'
bitkoop list-sites --sort-by store_domain       # Sort by domain name
bitkoop list-sites --all                        # Fetch and display all sites
```

### List Categories
List all available product categories with filtering and pagination.

```bash
bitkoop list-categories [options]
```

**Options:**
- `--name` - Filter by category name (partial match, e.g., 'electro' for electronics)
- `--page` - Page number for pagination (default: 1)
- `--limit` - Number of categories per page (default: 100 - shows all)
- `--sort-by` - Field to sort by: category_id, category_name (default: category_id)
- `--sort-order` - Sort direction: asc, desc (default: asc)

**Examples:**
```bash
bitkoop list-categories                         # List all categories (default limit=100)
bitkoop list-categories --limit 10              # Show only 10 categories per page
bitkoop list-categories --limit 10 --page 2     # Show second page (categories 11-20)
bitkoop list-categories --name electro          # Find categories containing 'electro'
bitkoop list-categories --sort-by category_name # Sort by name instead of ID
bitkoop list-categories --name phone --limit 5  # Find phone categories, show 5 per page
```

### Delete Code
Delete a coupon code (requires wallet authentication).

```bash
bitkoop delete-code <site> <code> [options]
```

**Arguments:**
- `site` - Site to delete code for
- `code` - Coupon code to delete

**Example:**
```bash
bitkoop delete-code amazon.com WELCOME10 --wallet.name my_wallet
```

### Recheck Code
Recheck a coupon code across ALL validators in the network (requires wallet authentication).

```bash
bitkoop recheck-code <site> <code> [options]
```

**Arguments:**
- `site` - Site to recheck code for
- `code` - Coupon code to recheck

**Example:**
```bash
bitkoop recheck-code amazon.com WELCOME10 --wallet.name my_wallet
```

### Rank
Displays the miner's leaderboard position, total points, and a summary of submitted coupons.

```bash
bitkoop rank
```

## Configuration

The CLI uses Bittensor wallet configuration for authenticated operations. You can specify wallet details using the standard Bittensor wallet arguments:

```bash
bitkoop submit-code site.com CODE --wallet.name my_wallet --wallet.hotkey my_hotkey
```

## License

MIT
