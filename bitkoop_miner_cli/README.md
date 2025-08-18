# BitKoop CLI – Setup & Usage

## 1. Installation

**Requirements:**
- Python 3.11-3.12
- `pip` (Python package manager)
- [bittensor_wallet](https://github.com/opentensor/bittensor) (or your custom wallet module)
- All dependencies in `requirements.txt`

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## 2. Project Structure

```
bitkoop_miner_cli/
├── business/         # Business logic (auth, codes, status, ranking)
├── commands/         # CLI command handlers (auth, submit, view, etc.)
├── utils/            # Utilities (display, formatting)
├── cli.py            # Main CLI entry point
```

## 3. Wallet Setup

You need a Bittensor wallet to authenticate and use the CLI.
If you don't have one, create it using the Bittensor wallet tools or your own wallet management.

**Example wallet directory:**
`~/.bittensor/wallets/<wallet_name>/<hotkey_name>`

## 4. CLI Installation Methods

### Option 1: Install Only Dependencies

```bash
pip install -r requirements.txt
```
- **How to run:**
  ```bash
  python -m bitkoop_miner_cli.cli <command> ...
  ```
- **Note:** The `bitkoop` command will **not** be available globally.

### Option 2: Install as a CLI Tool (Recommended)

To use the `bitkoop` command from anywhere, install the package with:

```bash
pip install .
```

- **How to run:**
  ```bash
  bitkoop <command> ...
  ```
- **Requirement:** Your `setup.py` or `pyproject.toml` must define a console script entry point:

  **setup.py example:**
  ```python
  entry_points={
      'console_scripts': [
          'bitkoop=bitkoop_miner_cli.cli:main',
      ],
  },
  ```
  **pyproject.toml example:**
  ```toml
  [project.scripts]
  bitkoop = "koupons_miner_cli.cli:main"
  ```

## 5. Help

For help on any command, use:
```bash
koupons <command> --help
```

Or for global help:
```bash
koupons --help
```

If not installed as a CLI tool, use:
```bash
python -m bitkoop_miner_cli.cli --help
```

## 6. Code Quality Tools

This project uses Ruff for linting and formatting Python code, along with pre-commit hooks to ensure code quality.

Install dependencies:
```bash
pip install ruff pre-commit
```

Usage
Manual linting and formatting
```bash
# Check for linting issues
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Format code
ruff format .
```
