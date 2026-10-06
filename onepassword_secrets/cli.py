import argparse
import logging
import sys
from importlib.metadata import version

from .commands import (
    create_local_secrets,
    edit_1password_fly_secrets,
    import_1password_secrets_to_fly,
    pull_local_secrets,
    push_local_secrets,
)
from .constants import DEFAULT_REMOTE_NAME
from .errors import UserError
from .logs import logger

try:
    APP_VERSION = version("1password-secrets")
except ImportError:
    APP_VERSION = "unknown"


def main():
    parser = argparse.ArgumentParser(
        description="1password-secrets is a set of utilities to sync 1Password secrets."
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
        help="show program's version number and exit",
    )

    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "run in debug mode, logging every command, HTTP request and response "
            "(authorization headers and the fly auth token are redacted)"
        ),
    )

    parser.add_argument(
        "--vault",
        type=str,
        default=None,
        help=(
            "Specify a vault name or id to operate on. "
            "Defaults to all vaults across the logged in account."
        ),
    )

    parser.add_argument(
        "--remote",
        type=str,
        default=DEFAULT_REMOTE_NAME,
        help='Construct secret name based on this git remote. Defaults to "origin"',
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    fly_parser = subparsers.add_parser("fly", help="manage fly secrets")
    fly_parser.add_argument("action", type=str, choices=["import", "edit"])
    fly_parser.add_argument("app_name", type=str, help="fly application name")

    local_parser = subparsers.add_parser("local", help="manage local secrets")
    local_subparsers = local_parser.add_subparsers(dest="action", required=True)

    local_subparsers.add_parser("pull")
    local_subparsers.add_parser("push")

    create_parser = local_subparsers.add_parser("create")
    create_parser.add_argument(
        "secrets_file_path",
        type=str,
        help="secrets file path",
    )

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        if args.subcommand == "fly":
            if args.action == "import":
                import_1password_secrets_to_fly(args.app_name, vault=args.vault)
            elif args.action == "edit":
                edit_1password_fly_secrets(args.app_name, vault=args.vault)

        elif args.subcommand == "local":
            if args.action == "pull":
                pull_local_secrets(remote=args.remote, vault=args.vault)
            elif args.action == "push":
                push_local_secrets(remote=args.remote, vault=args.vault)
            elif args.action == "create":
                create_local_secrets(args.secrets_file_path, vault=args.vault, remote=args.remote)

    except UserError:
        sys.exit(1)
