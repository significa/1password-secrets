"""High level workflows wiring 1Password, Fly and the local filesystem together."""

import json
import os
import subprocess
from datetime import UTC, datetime
from tempfile import NamedTemporaryFile

from rich.panel import Panel

from .constants import DATE_FORMAT, DEFAULT_ENV_FILE_NAME, DEFAULT_REMOTE_NAME
from .envs import format_duplicate_keys, get_duplicate_keys_from_envs, get_secrets_from_envs
from .fly import update_fly_secrets
from .git import get_secret_name_label_from_current_directory
from .logs import console, debug_command, logger
from .op import (
    create_1password_secrets,
    get_1password_env_file_item_id,
    get_envs_from_1password,
    get_filename_from_1password,
    get_item_share_link,
    update_1password_custom_field,
    update_1password_secrets,
)
from .prompts import SecretDiff, boolean_prompt, prompt_secret_diff
from .utils import get_file_contents


def import_1password_secrets_to_fly(app_id, vault=None):
    item_id = get_1password_env_file_item_id(f"fly:{app_id}", vault=vault)

    secrets = get_secrets_from_envs(
        get_envs_from_1password(item_id, vault=vault), source="the 1Password item"
    )

    logger.debug(f"Secrets loaded from env: {json.dumps(secrets, indent=2)}\n")

    update_fly_secrets(app_id, secrets)

    now_formatted = datetime.now(tz=UTC).strftime(DATE_FORMAT)
    update_1password_custom_field(item_id, "last imported at", now_formatted, vault=vault)


def edit_1password_fly_secrets(app_id, vault=None):
    item_id = get_1password_env_file_item_id(f"fly:{app_id}", vault=vault)

    current_raw_secrets = get_envs_from_1password(item_id, vault=vault)

    # Unlike the other commands, editing is how duplicates get fixed, so only warn here.
    # Saving is still blocked until the edited file no longer has duplicates.
    duplicate_keys = get_duplicate_keys_from_envs(current_raw_secrets)
    if duplicate_keys:
        console.print()
        console.print(
            Panel(
                "The 1Password item defines the following keys more than once: "
                f"{format_duplicate_keys(duplicate_keys)}\n"
                "[dim]Remove the duplicates in the editor, saving is blocked until you do.[/dim]",
                title="Warning",
                border_style="yellow",
            )
        )

    get_secrets_from_envs(current_raw_secrets, source="the 1Password item", allow_duplicates=True)

    # delete=False so that the file is still around for the editor to open on every platform,
    # cleaned up in the finally block below no matter how we leave this function.
    file = NamedTemporaryFile("w+", suffix=".env", delete=False)  # noqa: SIM115

    try:
        with file:
            file.writelines(current_raw_secrets)
            file.flush()

            console.print()
            console.print(
                Panel(
                    "[bold]Edit the secrets in your editor, then save and close the file to continue.[/bold]\n"
                    "[dim]Waiting for editor to close...[/dim]",
                    title="Editor",
                    border_style="cyan",
                )
            )

            editor_command_args = ["code", "--wait", "--disable-extensions", file.name]
            debug_command(editor_command_args)
            editor_output = subprocess.check_output(editor_command_args)  # noqa: S603
            debug_command(editor_command_args, output=editor_output, returncode=0)

            console.print("[green]Editor closed.[/green]")
            console.print()

            file.seek(0)
            new_raw_secrets = file.read()

        get_secrets_from_envs(new_raw_secrets, source="the edited file")

        update_1password_secrets(
            item_id,
            new_raw_secrets=new_raw_secrets,
            previous_raw_secrets=current_raw_secrets,
            vault=vault,
            allow_previous_duplicates=True,
        )
    finally:
        try:
            os.unlink(file.name)
        except FileNotFoundError:
            pass

    console.print()
    if boolean_prompt(f"Secrets updated in 1Password. Import to Fly app '{app_id}'"):
        import_1password_secrets_to_fly(app_id, vault=vault)


def pull_local_secrets(remote=DEFAULT_REMOTE_NAME, vault=None):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)
    item_id = get_1password_env_file_item_id(secret_note_label, vault=vault)

    secrets = get_envs_from_1password(item_id, vault=vault)
    get_secrets_from_envs(secrets, source="the 1Password item")

    env_file_name = get_filename_from_1password(item_id, vault=vault) or DEFAULT_ENV_FILE_NAME

    previous_raw_secrets = get_file_contents(env_file_name, raise_if_not_found=False)

    if previous_raw_secrets:
        get_secrets_from_envs(previous_raw_secrets, source=env_file_name)
        diff = prompt_secret_diff(
            previous_raw_secrets=previous_raw_secrets,
            new_raw_secrets=secrets,
            apply_prompt=f"Pull these changes into {env_file_name}",
            cosmetic_prompt=f"Pull the file into {env_file_name} anyway",
        )

        if diff == SecretDiff.IDENTICAL:
            console.print(f"[dim]No changes detected, {env_file_name} is already up to date[/dim]")
            return

    with open(env_file_name, "w") as file:
        file.writelines(secrets)

    console.print(f"[bold green]Successfully updated {env_file_name} from 1Password[/bold green]")


def push_local_secrets(remote=DEFAULT_REMOTE_NAME, vault=None):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)
    item_id = get_1password_env_file_item_id(secret_note_label, vault=vault)

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    secrets = get_file_contents(env_file_name, raise_if_not_found=True)
    get_secrets_from_envs(secrets, source=env_file_name)

    previous_raw_secrets = get_envs_from_1password(item_id, vault=vault)
    get_secrets_from_envs(previous_raw_secrets, source="the 1Password item")

    update_1password_secrets(
        item_id, secrets, previous_raw_secrets=previous_raw_secrets, vault=vault
    )

    console.print(
        f"[bold green]Successfully pushed secrets from {env_file_name} to 1Password[/bold green]"
    )


def create_local_secrets(secrets_file_path, vault=None, remote=DEFAULT_REMOTE_NAME):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)

    raw_secrets = get_file_contents(secrets_file_path, raise_if_not_found=True)
    get_secrets_from_envs(raw_secrets, source=secrets_file_path)

    title = f"{secrets_file_path} local development {secret_note_label}"

    item = create_1password_secrets(
        file_path=secrets_file_path, raw_secrets=raw_secrets, title=title, vault=vault
    )

    item_url = get_item_share_link(item["id"], vault=vault)

    app_url = item_url.replace("https://start.1password.com/", "onepassword://")

    console.print()
    console.print(f"[bold green]Item '{title}' created in 1Password![/bold green]")
    console.print()
    console.print(
        Panel(f"[link={item_url}]{item_url}[/link]", title="Web Link", border_style="blue")
    )
    console.print(Panel(f"[link={app_url}]{app_url}[/link]", title="App Link", border_style="blue"))
