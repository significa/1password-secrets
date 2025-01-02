import os
import re
from pathlib import Path

from setuptools import setup  # type: ignore

long_description = (Path(__file__).parent / "README.md").read_text()
requirements = (Path(__file__).parent / "requirements.txt").read_text().split("\n")

version = re.sub(r"^v", "", os.getenv("VERSION", "v0.0.1-dev"))

print(f"Publishing version {version}")

setup(
    name="1password-secrets",
    python_requires=">=3.10",
    version=version,
    description="1password-secrets is a set of utilities to sync 1Password secrets.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=requirements,
    entry_points={
        "console_scripts": ["1password-secrets = onepassword_secrets:main"],
    },
    license="MIT",
    url="https://github.com/significa/fly-1password-secrets",
    keywords="fly.io, 1password, secrets",
    author="Significa",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Utilities",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
