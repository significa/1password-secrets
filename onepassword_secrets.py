import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from io import StringIO
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values
from sgqlc.endpoint.http import HTTPEndpoint

FLY_GRAPHQL_ENDPOINT = "https://api.fly.io/graphql"
DATE_FORMAT = "%Y/%m/%d %H:%M:%S"
DEFAULT_ENV_FILE_NAME = ".env"
ONE_PASSWORD_FILE_PATH_FIELD_NAME = "file_name"  # noqa: S105
ONE_PASSWORD_NOTES_CONTENT_FIELD_NAME = "notesPlain"  # noqa: S105
ONE_PASSWORD_SECURE_NOTE_CATEGORY = "Secure Note"  # noqa: S105
DEFAULT_REMOTE_NAME = "origin"


class UserError(RuntimeError):
    pass


def _setup_logger():
    class Formatter(logging.Formatter):
        def format(self, record):
            if record.levelno == logging.INFO:
                self._style._fmt = "%(message)s"
            else:
                self._style._fmt = "%(levelname)s: %(message)s"
            return super().format(record)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(Formatter())
    logger.addHandler(stdout_handler)

    return logger


logger = _setup_logger()


def get_1password_env_file_item_id(title_substring, vault=None):
    secure_notes = json.loads(
        _run_1password_command(
            "item",
            "list",
            "--categories",
            ONE_PASSWORD_SECURE_NOTE_CATEGORY,
            vault=vault,
        )
    )

    item_ids = [item["id"] for item in secure_notes if title_substring in item["title"].split(" ")]

    if len(item_ids) == 0:
        raise_error(
            f"No 1password secure note found with a name containing {title_substring!r} "
            f"in vault {vault}"
            if vault
            else "across all vaults"
        )

    if len(item_ids) > 1:
        raise_error(
            f"Found {len(item_ids)} 1password secure notes with a name containing "
            f"{title_substring!r}, expected one. "
            "Rename or use different 1password vaults in combination with the `--vault` option."
        )

    return item_ids[0]


def get_item_from_1password(item_id, vault=None):
    return json.loads(_run_1password_command("item", "get", item_id, vault=vault))


def get_envs_from_1password(item_id, vault=None) -> str:
    item = get_item_from_1password(item_id, vault=vault)

    result = first(
        field.get("value")
        for field in item["fields"]
        if field["id"] == ONE_PASSWORD_NOTES_CONTENT_FIELD_NAME
    )
    if result is None or result == "":
        raise_error("Empty secrets, aborting")

    return result or ""


def get_filename_from_1password(item_id, vault=None):
    item = get_item_from_1password(item_id, vault=vault)

    return first(
        field.get("value")
        for field in item["fields"]
        if field["label"] == ONE_PASSWORD_FILE_PATH_FIELD_NAME
    )


def get_fly_auth_token():
    return json.loads(
        subprocess.check_output(["fly", "auth", "token", "--json"])  # noqa: S603, S607
    )["token"]


def _get_file_contents(filepath, raise_if_not_found=True):
    try:
        with open(filepath) as file:
            return file.read()
    except FileNotFoundError:
        if raise_if_not_found:
            raise_error(f"Env file {filepath!r} not found!")

        return None


def _boolean_prompt(prompt: str):
    user_input = ""
    while user_input not in ["y", "n"]:
        user_input = input(f"{prompt} (y/n): ").lower()

    return user_input == "y"


def _make_fly_graphql_request(graphql_query, variables):
    headers = {"Authorization": f"Bearer {get_fly_auth_token()}"}

    endpoint = HTTPEndpoint(FLY_GRAPHQL_ENDPOINT, headers)

    response = endpoint(query=graphql_query, variables=variables)

    logger.debug(
        f"Fly request:\n{graphql_query}\n{json.dumps(variables, indent=2)}\n\n"
        f"Fly response:\n{json.dumps(response, indent=2)}\n"
    )

    if response.get("errors") is not None:
        raise_error(json.dumps(response["errors"][0]))

    return response["data"]


def update_fly_secrets(app_id, secrets):
    secrets_input = [{"key": key, "value": value} for key, value in secrets.items()]

    last_update_secrets_response = _make_fly_graphql_request(
        """
        mutation(
            $appId: ID!
            $secrets: [SecretInput!]!
            $replaceAll: Boolean!
        ) {
            setSecrets(
                input: {
                    appId: $appId
                    replaceAll: $replaceAll
                    secrets: $secrets
                }
            ) {
                app {
                    name
                }
                release {
                    version
                }
            }
        }
        """,
        {"appId": app_id, "secrets": secrets_input, "replaceAll": True},
    )

    get_secrets_response = _make_fly_graphql_request(
        """
        query(
            $appName: String
        ) {
            app(name: $appName){
                secrets{
                name
                }
            }
        }
        """,
        {
            "appName": app_id,
        },
    )

    secrets_names_in_env_file = set(secrets.keys())
    secret_names_in_fly = {secret["name"] for secret in get_secrets_response["app"]["secrets"]}

    secrets_names_in_fly_only = secret_names_in_fly.difference(secrets_names_in_env_file)

    if len(secrets_names_in_fly_only) > 0 and _boolean_prompt(
        "The following secrets will be deleted from Fly: {}, Are you sure?".format(
            ", ".join(secrets_names_in_fly_only)
        )
    ):
        last_update_secrets_response = _make_fly_graphql_request(
            """
            mutation(
                $appId: ID!
                $secretNames: [String!]!
            ) {
                unsetSecrets(
                    input: {
                        appId: $appId
                        keys: $secretNames
                    }
                ){
                        release{
                    id
                    }
                }
            }
            """,
            {
                "appId": app_id,
                "secretNames": list(secrets_names_in_fly_only),
            },
        )

    release = last_update_secrets_response.get("setSecrets", {}).get("release", None)

    if release:
        release_version = release.get("version", "unknown")
        print(f"Releasing fly app {app_id} version {release_version}")
    else:
        print(
            "Fly secrets updated, no release created, "
            "make sure to trigger a re-deploy for the changes to apply."
        )


def _prompt_secret_diff(previous_raw_secrets, new_raw_secrets):
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
        if not _boolean_prompt("No changes detected, proceed?"):
            raise_error("Aborted by user")
        return

    if not _boolean_prompt(
        "Change summary\n{}\nProceed?".format(
            "\n".join(
                " {}: {}".format(label, ", ".join(items))
                for label, items in {
                    "Deleted": deleted_keys,
                    "Added": added_keys,
                    "Modified": keys_whos_value_changed,
                }.items()
                if len(items) != 0
            )
        )
    ):
        raise_error("Aborted by user")


def _run_1password_command(*args, vault=None, json_output=True):
    command_args = ["op", *args]

    if vault is not None:
        command_args.extend(["--vault", vault])

    if json_output:
        command_args.extend(["--format", "json"])

    logger.debug(
        "Running command: {}".format(
            " ".join((f'"{arg}"' if " " in arg else arg) for arg in command_args)
        )
    )

    return subprocess.check_output(command_args)  # noqa: S603


def create_1password_secrets(file_path, raw_secrets, title, vault=None):
    logger.debug("Creating 1password secret note")

    return json.loads(
        _run_1password_command(
            "item",
            "create",
            "--category",
            ONE_PASSWORD_SECURE_NOTE_CATEGORY,
            "--title",
            title,
            f"{ONE_PASSWORD_NOTES_CONTENT_FIELD_NAME}={raw_secrets}",
            f"{ONE_PASSWORD_FILE_PATH_FIELD_NAME}[text]={file_path}",
            _make_last_edited_1password_custom_field_cli_argument(),
            vault=vault,
        )
    )


def update_1password_secrets(item_id, new_raw_secrets, previous_raw_secrets=None, vault=None):
    if previous_raw_secrets is None:
        previous_raw_secrets = get_envs_from_1password(item_id)

    _prompt_secret_diff(
        previous_raw_secrets=previous_raw_secrets,
        new_raw_secrets=new_raw_secrets,
    )

    logger.debug(f"Updating 1password secret note content for item {item_id!r}")
    _run_1password_command(
        "item",
        "edit",
        item_id,
        f"notesPlain={new_raw_secrets}",
        _make_last_edited_1password_custom_field_cli_argument(),
        vault=vault,
    )


def update_1password_custom_field(item_id, field, value, vault=None):
    logger.debug(f"Updating 1password custom field for item {item_id!r}")
    _run_1password_command(
        "item",
        "edit",
        item_id,
        _make_1password_custom_field_cli_argument(field, value),
        vault=vault,
    )


def _make_1password_custom_field_cli_argument(field_name, value):
    prefix = "Generated by 1password-secrets"
    return f"{prefix}.{field_name}[text]={value}"


def _make_last_edited_1password_custom_field_cli_argument():
    now_formatted = datetime.now(tz=timezone.utc).strftime(DATE_FORMAT)

    return _make_1password_custom_field_cli_argument(
        field_name="last edited at",
        value=now_formatted,
    )


def get_secrets_from_envs(input: str):
    secrets = dotenv_values(stream=StringIO(input))

    keys_with_values_null_values = [key for key, value in secrets.items() if value is None]

    if len(keys_with_values_null_values) > 0:
        raise_error(
            "Failed to parse env file, values for the following keys are null: {}".format(
                ", ".join(keys_with_values_null_values)
            )
        )

    return secrets


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

    with NamedTemporaryFile("w+") as file:
        file.writelines(current_raw_secrets)
        file.flush()
        subprocess.check_output(["code", "--wait", file.name])  # noqa: S603, S607

        file.seek(0)
        new_raw_secrets = file.read()

    update_1password_secrets(
        item_id,
        new_raw_secrets=new_raw_secrets,
        previous_raw_secrets=current_raw_secrets,
        vault=vault,
    )

    if _boolean_prompt(
        "Secrets updated in 1password, " f"do you wish to import secrets to the fly app {app_id}?"
    ):
        import_1password_secrets_to_fly(app_id, vault=vault)


def pull_local_secrets(remote=DEFAULT_REMOTE_NAME, vault=None):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)
    item_id = get_1password_env_file_item_id(secret_note_label, vault=vault)

    secrets = get_envs_from_1password(item_id, vault=vault)

    env_file_name = get_filename_from_1password(item_id, vault=vault) or DEFAULT_ENV_FILE_NAME

    previous_raw_secrets = _get_file_contents(env_file_name, raise_if_not_found=False)

    if previous_raw_secrets:
        _prompt_secret_diff(
            previous_raw_secrets=previous_raw_secrets,
            new_raw_secrets=secrets,
        )

    with open(env_file_name, "w") as file:
        file.writelines(secrets)

    print(f"Successfully updated {env_file_name} from 1password")


def push_local_secrets(remote=DEFAULT_REMOTE_NAME, vault=None):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)
    item_id = get_1password_env_file_item_id(secret_note_label, vault=vault)

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    secrets = _get_file_contents(env_file_name, raise_if_not_found=True)

    update_1password_secrets(item_id, secrets, vault=vault)

    print(f"Successfully pushed secrets from {env_file_name} to 1password")


def create_local_secrets(secrets_file_path, vault=None, remote=DEFAULT_REMOTE_NAME):
    secret_note_label = get_secret_name_label_from_current_directory(remote=remote)

    raw_secrets = _get_file_contents(secrets_file_path, raise_if_not_found=True)

    title = f"{secrets_file_path} local development {secret_note_label}"

    item = create_1password_secrets(
        file_path=secrets_file_path, raw_secrets=raw_secrets, title=title, vault=vault
    )

    item_url = (
        _run_1password_command(
            "item",
            "get",
            item["id"],
            "--share-link",
            vault=vault,
            json_output=False,
        ).decode("utf-8")
    ).strip()

    print(f"Item {title!r} created in 1password!\n")
    print(item_url)
    print(item_url.replace("https://start.1password.com/", "onepassword://"))


def _get_git_remote_name(remote=DEFAULT_REMOTE_NAME) -> tuple[str | None, str | None]:
    git_repository_regex = r"^(\w+)(:\/\/|@)([^\/:]+)[\/:]([^\/:]+)\/(.+).git$"

    git_remote_url = None

    try:
        git_remote_url = (
            subprocess.check_output(  # noqa: S603
                [  # noqa: S607
                    "git",
                    "config",
                    "--get",
                    f"remote.{remote}.url",
                ]
            )
            .decode("utf-8")
            .strip()
        )

    except FileNotFoundError:
        return ("git not in the PATH", None)

    except subprocess.CalledProcessError as error:
        exit_code, _command = error.args

        if exit_code == 1:
            return (f"Either not in a git repository or remote {remote!r} is not set", None)

        return (f"Failed to retrieve the git remote {remote!r} url", None)

    regex_match = re.match(git_repository_regex, git_remote_url)

    if regex_match is None:
        return (f'Failed to parse git remote "{remote}"', None)

    return (
        None,
        f"{regex_match.group(4)}/{regex_match.group(5)}",
    )


def get_secret_name_label_from_current_directory(remote=DEFAULT_REMOTE_NAME) -> str:
    """
    Returns a predictable label for identifying the secrets based on the current directory.
    If within a git repository with a remote named "origin" (and git is installed), it will output
     something like: `repo:my-org/my-repo` or `repo:my-org/my-team/my-repo`.
    Otherwise it will return the name of the directory as `local-dir:my-directory-name`.
    """

    error_message, git_remote_name = _get_git_remote_name(remote=remote)

    if not error_message:
        return f"repo:{git_remote_name}"

    directory_name = os.path.basename(os.getcwd())
    label = f"local-dir:{directory_name}"

    print(f"{error_message}, using the label based on the current directory: {label!r}")
    return label


def raise_error(message):
    print(message)
    raise UserError(message)


def first(iterable):
    try:
        return next(iterable)
    except StopIteration:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="1password-secrets is a set of utilities to sync 1Password secrets."
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        type=bool,
        default=False,
        help="run in debug mode",
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


if __name__ == "__main__":
    main()
