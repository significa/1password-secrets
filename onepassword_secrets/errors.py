from typing import NoReturn

from .logs import console


class UserError(RuntimeError):
    pass


def raise_error(message) -> NoReturn:
    console.print(f"[bold red]Error:[/bold red] {message}")
    raise UserError(message)
