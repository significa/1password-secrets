from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / "README.md").read_text()

setup(
    name="fly-1password-secrets",
    version="0.0.1",
    description="CLI to sync secrets stored in 1Password with a fly application.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=[],
    license='MIT',
    url="https://github.com/significa/fly-1password-secrets",
    keywords="fly.io, 1password, secrets",
    author="Significa",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
    ],
)
