import json
import logging

from rich.console import Console

from .constants import REDACTED_PLACEHOLDER, SENSITIVE_HEADER_NAMES

console = Console()


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


def redact_headers(headers) -> dict:
    return {
        name: (REDACTED_PLACEHOLDER if name.lower() in SENSITIVE_HEADER_NAMES else value)
        for name, value in dict(headers or {}).items()
    }


def format_command(command_args) -> str:
    return " ".join((f'"{arg}"' if " " in arg else arg) for arg in command_args)


def debug_enabled() -> bool:
    return logger.isEnabledFor(logging.DEBUG)


def debug_request(method, url, headers, json_body) -> None:
    if not debug_enabled():
        return

    lines = [f"Request: {method} {url}", "Request headers:"]
    lines += [f"  {name}: {value}" for name, value in redact_headers(headers).items()]

    if json_body is not None:
        lines += ["Request body:", json.dumps(json_body, indent=2)]

    logger.debug("\n".join(lines))


def debug_response(response) -> None:
    if not debug_enabled():
        return

    lines = [f"Response: {response.status_code}", "Response headers:"]
    lines += [f"  {name}: {value}" for name, value in redact_headers(response.headers).items()]
    lines += ["Response body:", response.text]

    logger.debug("\n".join(lines))


def debug_command(command_args, output=None, returncode=None, redact_output=False) -> None:
    if not debug_enabled():
        return

    lines = [f"Running command: {format_command(command_args)}"]

    if returncode is not None:
        lines.append(f"Exit code: {returncode}")

    if output is not None:
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")

        lines += ["Output:", REDACTED_PLACEHOLDER if redact_output else output]

    logger.debug("\n".join(lines))
