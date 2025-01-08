[![PyPI version 1password-secrets](https://raw.githubusercontent.com/significa/.github/main/assets/significa-github-banner-small.png)](https://significa.co)

# 1password-secrets

[![PyPI version 1password-secrets](https://img.shields.io/pypi/v/1password-secrets.svg)](https://pypi.python.org/pypi/1password-secrets/)
[![CI/CD](https://github.com/significa/1password-secrets/actions/workflows/ci-cd.yaml/badge.svg)](https://github.com/significa/1password-secrets/actions/workflows/ci-cd.yaml)

1password-secrets is a CLI utility to sync 1Password secrets (env files). It enables:

- Seamless sharing of _local_ secrets used for development.
  Developers starting out in a project can just use this tool to retrieve the `.env` file needed for
  local development.
  Likewise it is also simple to push any local changes to the 1password vault.

- More secure and simpler method of managing Fly.io secrets.
  By default, Fly secrets must be managed by `flyctl`. This means that when setting secrets in
  production, developers must use `flyctl` to pass credentials via arguments - risking credentials
  being stored in their histories. Alternatively, one must write secrets in a file and run
  `flyctl secrets import`. This works well, but you must ensure everything is synced to a
  secret/password manager and then delete the file.
  1password-secrets enables a leaner management of secrets via 1password. When passing a fly app name, it
  automatically finds and imports secrets on 1password to Fly. This way you ensure
  developers always keep secrets up-to-date and never in any files on disk.

Motivation: Using 1password avoids the need for another external secret management tool and keeps
the access control in a centralised place that we already use.

## Getting started

### Requirements

- Install the required dependencies:

  1Password >= `8.9.13`

  1Password CLI >= `2.13.1`

  Python >= `3.10`

  flyctl >= `0.0.451` (optional)

  ```sh
  brew install --cask 1password 1password-cli && \
  brew install flyctl
  ```

  More information and installation instructions for other systems can be found
  [in the 1password documentation](https://developer.1password.com/docs/cli/get-started/).

- Allow 1Password to connect to 1Password-CLI by going to 1Password's `Settings` -> `Developer` ->
  `Command-Line Interface (CLI)` and select `Integrate with 1Password CLI`.

- Sign into your 1Password desktop and if you wish to use the fly integration, also make sure
  the CLI is authenticated.

### Installation

In order to keep your system tidy and without conflicts in your global and user packages,
we recommend [pipx](https://github.com/pypa/pipx?tab=readme-ov-file):

```
pipx install 1password-secrets
```

This should do the trick for all systems.
Adapt the installation command to fit your preferred tool.

Use `pipx upgrade 1password-secrets` to update to the latest release.

## Usage

### Local

1password-secrets will allow you to `create`, `pull` and `push` secrets to a 1password secure note
with `repo:<owner>/<repo>` or `local:<dir-basename>` in its name. `repo` is used when within a valid
git repository with remote "origin" set.

The remote name can be changed with the `--remote` switch if you use a different remote
(e.g. `upstream`)

By default it syncs to `./.env` file, this can be overridden with a `file_name` field in 1password
containing the desired relative file path.

By default it searches items across 1password vaults. Restrict the search to a single vault with the
`--vault` switch.

- To bootstrap a 1Password secret matching the current repo/directory, run:
  `1password-secrets local create ./env`  
  Where `./env` is an existing file you want to use.

- To get secrets from 1Password, run:
  `1password-secrets local pull`

- To push the local changes to 1Password, run:
  `1password-secrets local push`

### Fly

Make sure you have a Secure Note in 1Password by having `fly:<fly-app-name>` in the title. `fly-app-name`
is the name of your fly application.

As with `Local` secrets above, you can specify a single 1Password vault by name or id with the
`--vault` option.

- To import secrets to fly, run:
  `1password-secrets fly import <fly-app-name>`

- Secrets can be edited directly on the 1Password app or by using the command:
  `1password-secrets fly edit <fly-app-name>`

## Development

- Ensure you have `make` installed.
- Create a virtual environment: `make setup-venv`.
- Activate the virtual environment: `source ./venv/bin/activate`.
- Install dependencies: `make install-deps`.

Then you can install (link) the repo globally with `make local-install`.

Before pushing any changes ensure your code is properly formatted with `make lint`.
Auto format the code with `make format`
