"""High level workflows wiring 1Password, Fly and the local filesystem together."""

import json
import subprocess
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile

from rich.panel import Panel

from .constants import DATE_FORMAT, DEFAULT_ENV_FILE_NAME, DEFAULT_REMOTE_NAME
from .envs import get_secrets_from_envs
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
from .prompts import boolean_prompt, prompt_secret_diff
from .utils import get_file_contents


def import_1password_secrets_to_fly(app_id, vault=None):
    item_id = get_1password_env_file_item_id(f"fly:{app_id}", vault=vault)

    secrets = get_secrets_from_envs(get_envs_from_1password(item_id, vault=vault))

    logger.debug(f"Secrets loaded from env: {json.dumps(secrets, indent=2)}\n")

    update_fly_secrets(app_id, secrets)

    now_formatted = datetime.now(tz=timezone.utc).strftime(DATE_FORMAT)
    update_1password_custom_field(item_id, "last imported at", now_formatted, vault=vault)


def edit_1password_fly_secrets(app_id, vault=None):
    item_id = get_1password_env_file_item_id(f"fly:{app_id}", vault=vault)

    current_raw_secrets = get_envs_from_1password(item_id, vault=vault)

    with NamedTemporaryFile("w+", suffix=".env") as file:
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

    update_1password_secrets(
        item_id,
        new_raw_secrets=new_raw_secrets,
        previous_raw_secrets=current_raw_secrets,
        vault=vault,
    )

    console.print()
    if boolean_prompt(f"Secrets updated in 1Password. Import to Fly app '{app_id}'"):
        import_1password_secrets_to_fly(app_id, vault=vault)


def pull_local_secrets(remote=DEFAULT_REMOTE_NAME, vault=None):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)
    item_id = get_1password_env_file_item_id(secret_note_label, vault=vault)

    secrets = get_envs_from_1password(item_id, vault=vault)

    env_file_name = get_filename_from_1password(item_id, vault=vault) or DEFAULT_ENV_FILE_NAME

    previous_raw_secrets = get_file_contents(env_file_name, raise_if_not_found=False)

    if previous_raw_secrets:
        prompt_secret_diff(
            previous_raw_secrets=previous_raw_secrets,
            new_raw_secrets=secrets,
        )

    with open(env_file_name, "w") as file:
        file.writelines(secrets)

    console.print(f"[bold green]Successfully updated {env_file_name} from 1Password[/bold green]")


def push_local_secrets(remote=DEFAULT_REMOTE_NAME, vault=None):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)
    item_id = get_1password_env_file_item_id(secret_note_label, vault=vault)

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    secrets = get_file_contents(env_file_name, raise_if_not_found=True)

    update_1password_secrets(item_id, secrets, vault=vault)

    console.print(
        f"[bold green]Successfully pushed secrets from {env_file_name} to 1Password[/bold green]"
    )


def create_local_secrets(secrets_file_path, vault=None, remote=DEFAULT_REMOTE_NAME):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)

    raw_secrets = get_file_contents(secrets_file_path, raise_if_not_found=True)

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
