"""
Display utilities for the BitKoop CLI using Rich.
"""

import ast
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from bitkoop_miner_cli.constants import FIELD_DISPLAY_NAMES

console = Console()


class CouponOperation(Enum):
    SUBMIT = "Submit"
    RECHECK = "Recheck"
    DELETE = "Delete"


@dataclass
class ValidationError:
    field: Optional[str]
    message: str
    validator_url: Optional[str] = None

    def __str__(self) -> str:
        if self.field:
            return f"{self.field}: {self.message}"
        return self.message


def display_panel(title: str, content: str, border_style: str = "blue"):
    """Display a panel with a title and content."""
    console.print(Panel.fit(content, title=title, border_style=border_style))


def display_table(title: str, columns: list, rows: list):
    """
    Display a table with the given title, columns, and rows.

    Args:
        title: The title of the table
        columns: List of tuples (name, style) for column headers
        rows: List of row data
    """
    table = Table(title=title)

    for column_name, style in columns:
        table.add_column(column_name, style=style)

    for row in rows:
        table.add_row(*row)

    console.print(table)


def display_progress(description: str, func):
    """
    Display a progress indicator while executing a function.

    Args:
        description: Description of the task
        func: Function to execute while showing progress

    Returns:
        The result of the function
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description=description, total=None)
        return func()


def confirm_action(message: str) -> bool:
    """
    Ask for confirmation before performing an action.

    Args:
        message: The confirmation message

    Returns:
        True if confirmed, False otherwise
    """
    return Confirm.ask(message)


def print_success(message: str):
    """Print a success message."""
    console.print(f"[green]{message}[/green]")


def print_error(message: str):
    """Print an error message."""
    console.print(f"[red]✗ {message}[/red]")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[blue]i {message}[/blue]")


def handle_site_not_found_error(site: str):
    """Handle site not found error with user-friendly message."""
    print_error(f"Site '{site}' is not registered in the system")
    print_info("Please verify the site URL is correct and registered")


def handle_connection_error(details: str = None):
    """Handle connection errors with user-friendly message."""
    print_error("Unable to communicate with the system")
    if details:
        console.print(f"[dim]Details: {details}[/dim]")


def handle_validation_error(message: str):
    """Handle validation errors with user-friendly message."""
    print_error(f"Validation error: {message}")


def handle_unexpected_error(error: str):
    """Handle unexpected errors with user-friendly message."""
    print_error(f"An unexpected error occurred: {error}")
    print_info("If this error persists, please contact support")


def parse_validator_errors(error_data: Any) -> list[ValidationError]:
    """Extract and parse errors from validator responses."""
    errors = []

    if isinstance(error_data, str):
        try:
            parsed = ast.literal_eval(error_data)
            if isinstance(parsed, list):
                error_data = parsed
        except (ValueError, SyntaxError):
            try:
                parsed = json.loads(error_data)
                if isinstance(parsed, list):
                    error_data = parsed
            except (ValueError, json.JSONDecodeError):
                return [ValidationError(None, error_data)]

    if isinstance(error_data, list):
        seen = set()
        for err in error_data:
            if isinstance(err, dict):
                field = None
                msg = err.get("msg", "")

                if err.get("loc") and isinstance(err["loc"], list):
                    loc_parts = [loc for loc in err["loc"] if loc != "body"]
                    field = loc_parts[-1] if loc_parts else None

                if msg.startswith("Value error, "):
                    msg = msg[13:]
                msg = msg.strip().rstrip("\n")

                if field and msg.lower().startswith(f"{field.lower()} "):
                    msg = msg[len(field) + 1 :].strip()
                elif field and msg.lower().startswith(f"{field.lower()}: "):
                    msg = msg[len(field) + 2 :].strip()

                error_key = (field, msg) if field else msg
                if error_key not in seen:
                    seen.add(error_key)
                    errors.append(ValidationError(field, msg))

    return errors if errors else [ValidationError(None, str(error_data))]


def extract_validator_errors_from_results(
    results: list[dict[str, Any]],
) -> dict[str, list[ValidationError]]:
    """
    Extract validation errors from validator results.

    Returns:
        Dict mapping validator URLs to their validation errors
    """
    validator_errors = {}

    for result in results:
        if not result.get("success", False):
            validator_url = result.get("validator_url", "Unknown validator")
            error_to_parse = None

            if result.get("error"):
                error_to_parse = result["error"]
            elif result.get("data") and isinstance(result["data"], dict):
                data = result["data"]
                if data.get("detail"):
                    error_to_parse = data["detail"]
                elif data.get("error"):
                    error_to_parse = data["error"]
                elif data.get("data") and isinstance(data["data"], dict):
                    nested_data = data["data"]
                    if nested_data.get("detail"):
                        error_to_parse = nested_data["detail"]

            if error_to_parse:
                errors = parse_validator_errors(error_to_parse)
                for error in errors:
                    error.validator_url = validator_url
                validator_errors[validator_url] = errors

    return validator_errors


def get_field_display_name(field: str) -> str:
    """Get the display name for a field, with fallback to formatted field name."""
    return FIELD_DISPLAY_NAMES.get(field, field.replace("_", " ").capitalize())


def display_validator_errors(validator_errors: dict[str, list[ValidationError]]):
    """Display errors from each validator separately."""
    for validator_url, errors in validator_errors.items():
        url_match = re.search(r"https?://([^:/]+)", validator_url)
        validator_id = url_match.group(1) if url_match else validator_url

        if len(errors) == 1 and not errors[0].field:
            console.print(
                f"[red]❌ Validator {validator_id} returned an error: "
                f'"{errors[0].message}"[/red]'
            )
        else:
            console.print(f"[red]❌ Validator {validator_id} returned errors:[/red]")
            for error in errors:
                if error.field:
                    field_name = get_field_display_name(error.field)
                    msg = error.message.rstrip(".")
                    console.print(f'[red]   • "{field_name}": {msg}[/red]')
                else:
                    console.print(f"[red]   • {error.message}[/red]")


def display_general_errors(errors: list[ValidationError]):
    """Display general validation errors without validator context."""
    console.print("[red]❌ Validation errors:[/red]")

    seen = set()
    for error in errors:
        error_key = (error.field, error.message)
        if error_key not in seen:
            seen.add(error_key)
            if error.field:
                field_name = get_field_display_name(error.field)
                msg = error.message.rstrip(".")
                console.print(f'[red]   • "{field_name}": {msg}[/red]')
            else:
                console.print(f"[red]   • {error.message}[/red]")


def display_coupon_error(
    code: str, operation: CouponOperation, result: dict[str, Any]
) -> bool:
    """
    Display unified error panel for coupon operations with validator errors.

    Args:
        code: Coupon code that failed
        operation: Type of operation (SUBMIT, RECHECK, DELETE)
        result: Operation result dictionary

    Returns:
        bool: True if error was displayed, False if operation succeeded
    """
    if result.get("success", False):
        return False

    if result.get("results"):
        validator_errors = extract_validator_errors_from_results(result["results"])
        if validator_errors:
            display_validator_errors(validator_errors)
    elif result.get("error"):
        errors = parse_validator_errors(result["error"])
        if errors and any(e.field for e in errors):
            display_general_errors(errors)
        else:
            console.print(f"[red]❌ Validation failed: {result['error']}[/red]")

    title = Text(f'Code "{code}" – {operation.value} Failed', style="bold red")
    content_lines = [
        "[bright_white]Please check out the validators' error logs.[/bright_white]",
        "[bright_white]If that doesn't seem right, feel free to reach "
        "out to the BitKoop community.[/bright_white]",
    ]
    panel = Panel(
        "\n".join(content_lines), title=title, border_style="red", expand=False
    )
    console.print(panel)

    return True
