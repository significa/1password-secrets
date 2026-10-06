import os
import re
import subprocess

from .constants import DEFAULT_REMOTE_NAME
from .logs import console, debug_command


def get_git_remote_name(remote=DEFAULT_REMOTE_NAME) -> tuple[str | None, str | None]:
    git_repository_regex = r"^(\w+)(:\/\/|@)([^\/:]+)[\/:]([^\/:]+)\/(.+).git$"

    git_remote_url = None
    command_args = ["git", "config", "--get", f"remote.{remote}.url"]

    try:
        git_remote_url = (
            subprocess.check_output(command_args)  # noqa: S603
            .decode("utf-8")
            .strip()
        )
        debug_command(command_args, output=git_remote_url, returncode=0)

    except FileNotFoundError:
        debug_command(command_args, output="git not in the PATH")
        return ("git not in the PATH", None)

    except subprocess.CalledProcessError as error:
        exit_code, _command = error.args
        debug_command(command_args, returncode=exit_code)

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

    error_message, git_remote_name = get_git_remote_name(remote=remote)

    if not error_message:
        return f"repo:{git_remote_name}"

    directory_name = os.path.basename(os.getcwd())
    label = f"local-dir:{directory_name}"

    console.print(
        f"[dim]{error_message}, using the label based on the current directory: {label!r}[/dim]"
    )
    return label
