"""
Display utilities for the Koupons CLI using Rich.
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

# Initialize Rich console
console = Console()


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
    console.print(f"[green]✓ {message}[/green]")


def print_error(message: str):
    """Print an error message."""
    console.print(f"[red]✗ {message}[/red]")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[blue]ℹ {message}[/blue]")


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
