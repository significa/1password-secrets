import os
import re
from pathlib import Path

from setuptools import setup  # type: ignore

long_description = (Path(__file__).parent / "README.md").read_text()
requirements = (Path(__file__).parent / "requirements.txt").read_text().split("\n")

version = re.sub(r"^v", "", os.getenv("VERSION", "v0.1.0-dev"))

print(f"Publishing version {version}")

setup(
    name="1password-secrets",
    python_requires=">=3.10",
    version=version,
    description="1password-secrets is a set of utilities to sync 1password secrets.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=requirements,
    py_modules=["onepassword_secrets"],
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
        "Topic :: Utilities",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
)
