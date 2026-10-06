"""Interactions with Fly.io: the machines REST API and the `fly` CLI."""

import json
import subprocess

import requests

from .constants import FLY_API_TIMEOUT_SECONDS, FLY_MACHINES_API_ENDPOINT
from .errors import raise_error
from .logs import console, debug_command, debug_request, debug_response
from .prompts import boolean_prompt


def get_fly_auth_token():
    command_args = ["fly", "auth", "token", "--json"]
    output = subprocess.check_output(command_args)  # noqa: S603
    debug_command(command_args, output=output, returncode=0, redact_output=True)

    return json.loads(output)["token"]


def make_fly_api_request(
    method,
    path,
    json_body=None,
    token=None,
    status_message="Communicating with Fly.io",
):
    url = f"{FLY_MACHINES_API_ENDPOINT}{path}"
    headers = {
        "Authorization": f"Bearer {token or get_fly_auth_token()}",
        "Content-Type": "application/json",
    }

    debug_request(method, url, headers, json_body)

    with console.status(f"[bold cyan]{status_message}...", spinner="dots"):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=FLY_API_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise_error(f"Failed to reach the Fly API: {error}")

    debug_response(response)

    if not response.ok:
        try:
            body = response.json()
        except ValueError:
            body = response.text

        message = body.get("error") if isinstance(body, dict) else body
        raise_error(f"Fly API error ({response.status_code}): {message or 'unknown error'}")

    if not response.content:
        return None

    try:
        return response.json()
    except ValueError:
        return None


def get_fly_secret_names(app_id, token=None) -> set[str]:
    response = (
        make_fly_api_request(
            "GET",
            f"/apps/{app_id}/secrets",
            token=token,
            status_message="Fetching current Fly secrets",
        )
        or {}
    )

    return {secret["name"] for secret in response.get("secrets") or [] if secret.get("name")}


def set_fly_secrets(app_id, values, token=None) -> None:
    make_fly_api_request(
        "POST",
        f"/apps/{app_id}/secrets",
        json_body={"values": values},
        token=token,
        status_message="Uploading secrets to Fly",
    )


def deploy_fly_secrets(app_id):
    """Deploy secrets to a Fly app using the fly CLI."""
    console.print()
    console.print(f"[bold cyan]Deploying secrets to Fly app '{app_id}'...[/bold cyan]")
    console.print()

    command_args = ["fly", "secrets", "deploy", "-a", app_id]
    debug_command(command_args)

    try:
        result = subprocess.run(command_args, check=False)  # noqa: S603
    except FileNotFoundError:
        raise_error("The 'fly' CLI was not found. See https://fly.io/docs/flyctl/install/")

    debug_command(command_args, returncode=result.returncode)

    if result.returncode != 0:
        raise_error(f"Failed to deploy secrets (exit code {result.returncode})")

    console.print()
    console.print(f"[bold green]Secrets deployed to Fly app '{app_id}'[/bold green]")


def update_fly_secrets(app_id, secrets):
    token = get_fly_auth_token()

    secret_names_in_fly = get_fly_secret_names(app_id, token=token)

    secrets_names_in_fly_only = secret_names_in_fly.difference(secrets.keys())

    deletions = {}

    if len(secrets_names_in_fly_only) > 0 and boolean_prompt(
        "The following secrets will be deleted from Fly.io: {}. Are you sure".format(
            ", ".join(sorted(secrets_names_in_fly_only))
        )
    ):
        deletions = dict.fromkeys(secrets_names_in_fly_only, None)

    values = {**secrets, **deletions}

    if not values:
        console.print()
        console.print("[dim]No secret changes to push to Fly.[/dim]")
        return

    set_fly_secrets(app_id, values, token=token)

    console.print()
    console.print(f"[bold green]Secrets staged on Fly app '{app_id}'[/bold green]")

    if boolean_prompt("Deploy secrets now (run fly secrets deploy)?"):
        deploy_fly_secrets(app_id)
