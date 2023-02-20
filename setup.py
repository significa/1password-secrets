import os
from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / "README.md").read_text()
requirements = (Path(__file__).parent / "requirements.txt").read_text().split("\n")


setup(
    name="1password-secrets",
    version=os.getenv("VERSION", "0.0.1"),
    description="1pasword-secrets is a set of utilities to sync 1Password secrets.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            '1password-secrets = 1password_secrets:main'
        ],
    },
    license='MIT',
    url="https://github.com/significa/fly-1password-secrets",
    keywords="fly.io, 1password, secrets",
    author="Significa",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
    ],
)
