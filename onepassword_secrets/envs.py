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
            lines_by_key[binding.key].append(binding.original.line)

    return {key: lines for key, lines in lines_by_key.items() if len(lines) > 1}


def get_secrets_from_envs(input: str, source: str = "env file"):
    duplicate_keys = get_duplicate_keys_from_envs(input)

    if len(duplicate_keys) > 0:
        raise_error(
            "Failed to parse {}, the following keys are defined more than once: {}. "
            "Remove the duplicates before proceeding.".format(
                source,
                ", ".join(
                    f"{key} (lines {', '.join(str(line) for line in lines)})"
                    for key, lines in duplicate_keys.items()
                ),
            )
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
