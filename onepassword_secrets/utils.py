from typing import Literal, overload

from .errors import raise_error


def first(iterable):
    try:
        return next(iterable)
    except StopIteration:
        return None


@overload
def get_file_contents(filepath, raise_if_not_found: Literal[True] = True) -> str: ...


@overload
def get_file_contents(filepath, raise_if_not_found: bool) -> str | None: ...


def get_file_contents(filepath, raise_if_not_found=True) -> str | None:
    try:
        with open(filepath) as file:
            return file.read()
    except FileNotFoundError:
        if raise_if_not_found:
            raise_error(f"Env file {filepath!r} not found!")

        return None
