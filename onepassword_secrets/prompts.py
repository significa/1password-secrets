from enum import StrEnum

import inquirer
from rich.table import Table
from rich.text import Text

from .envs import get_secrets_from_envs
from .errors import raise_error
from .logs import console


def boolean_prompt(prompt: str, default: bool = False) -> bool:
    """Prompt user for confirmation using inquirer."""
    questions = [
        inquirer.Confirm(
            "confirm",
            message=prompt,
            default=default,
        ),
    ]
    answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
    if answers is None:
        raise_error("Aborted by user")
    return answers["confirm"]


class SecretDiff(StrEnum):
    """Outcome of comparing two raw env file contents."""

    CHANGED = "changed"
    """Env var keys were added, removed or had their value changed."""

    COSMETIC = "cosmetic"
    """No env var differences, but the file contents differ (comments, ordering, spacing)."""

    IDENTICAL = "identical"
    """Both files are equivalent."""


def prompt_secret_diff(
    previous_raw_secrets,
    new_raw_secrets,
    apply_prompt: str = "Apply these changes",
    cosmetic_prompt: str = "Apply these changes anyway",
) -> SecretDiff:
    """Show the diff between two env files and ask for confirmation when relevant.

    Returns the kind of difference found. Nothing is prompted when the contents are
    equivalent - it is up to the caller to decide what to do in that case.
    """
    previous_parsed_secrets = get_secrets_from_envs(previous_raw_secrets)
    new_parsed_secrets = get_secrets_from_envs(new_raw_secrets)

    previous_keys = set(previous_parsed_secrets.keys())
    new_keys = set(new_parsed_secrets.keys())

    deleted_keys = previous_keys.difference(new_keys)
    added_keys = new_keys.difference(previous_keys)
    keys_whos_value_changed = [
        key
        for key in previous_keys.intersection(new_keys)
        if previous_parsed_secrets[key] != new_parsed_secrets[key]
    ]

    if len(deleted_keys) == 0 and len(added_keys) == 0 and len(keys_whos_value_changed) == 0:
        if previous_raw_secrets.strip() == new_raw_secrets.strip():
            return SecretDiff.IDENTICAL

        console.print(
            "[dim]No environment variable differences, "
            "but the file structure or comments changed[/dim]"
        )
        console.print()

        if not boolean_prompt(cosmetic_prompt, default=True):
            raise_error("Aborted by user")

        return SecretDiff.COSMETIC

    # Build a rich table for the diff
    table = Table(title="Change Summary", show_header=True, header_style="bold")
    table.add_column("Type", style="bold")
    table.add_column("Keys")

    if deleted_keys:
        table.add_row(
            Text("Deleted", style="red"),
            Text(", ".join(sorted(deleted_keys)), style="red"),
        )
    if added_keys:
        table.add_row(
            Text("Added", style="green"),
            Text(", ".join(sorted(added_keys)), style="green"),
        )
    if keys_whos_value_changed:
        table.add_row(
            Text("Modified", style="yellow"),
            Text(", ".join(sorted(keys_whos_value_changed)), style="yellow"),
        )

    console.print(table)
    console.print()

    if not boolean_prompt(apply_prompt):
        raise_error("Aborted by user")

    return SecretDiff.CHANGED
