from io import StringIO

from dotenv import dotenv_values

from .errors import raise_error


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
