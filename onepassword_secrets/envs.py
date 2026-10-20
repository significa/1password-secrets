from collections import defaultdict
from io import StringIO

from dotenv import dotenv_values
from dotenv.parser import parse_stream

from .errors import raise_error


def get_duplicate_keys_from_envs(input: str) -> dict[str, list[int]]:
    """Map each key defined more than once to the line numbers where it is defined."""
    lines_by_key = defaultdict(list)

    for binding in parse_stream(StringIO(input)):
        if binding.key is not None:
            # The parser attaches leading blank lines to the binding that follows them,
            # so skip past them to report the line the key is actually on.
            original = binding.original.string
            leading_whitespace = original[: len(original) - len(original.lstrip())]
            line_offset = leading_whitespace.replace("\r\n", "\n").replace("\r", "\n").count("\n")
            lines_by_key[binding.key].append(binding.original.line + line_offset)

    return {key: lines for key, lines in lines_by_key.items() if len(lines) > 1}


def format_duplicate_keys(duplicate_keys: dict[str, list[int]]) -> str:
    return ", ".join(
        f"{key} (lines {', '.join(str(line) for line in lines)})"
        for key, lines in duplicate_keys.items()
    )


def get_secrets_from_envs(input: str, source: str = "env file", allow_duplicates: bool = False):
    duplicate_keys = get_duplicate_keys_from_envs(input)

    if len(duplicate_keys) > 0 and not allow_duplicates:
        raise_error(
            f"Failed to parse {source}, the following keys are defined more than once: "
            f"{format_duplicate_keys(duplicate_keys)}. Remove the duplicates before proceeding."
        )

    secrets = dotenv_values(stream=StringIO(input))

    keys_with_values_null_values = [key for key, value in secrets.items() if value is None]

    if len(keys_with_values_null_values) > 0:
        raise_error(
            "Failed to parse {}, values for the following keys are null: {}".format(
                source, ", ".join(keys_with_values_null_values)
            )
        )

    return secrets
