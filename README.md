# 1password-secrets

1pasword-secrets is a set of utilities to sync 1Password secrets.

## Getting started
### Requirements

 - Install required dependencies
   1Password >= `8.9.13`
   1Password CLI >=  `2.13.1`
   flyctl >= `0.0.451`
   ```
   brew install --cask 1password 1password-cli && \
   brew install flyctl
   ```

 - Allow 1Password to connect to 1Password-CLI by going to `Settings` -> `Developer` -> `Command-Line Interface (CLI)` and select `Connect with 1Password CLI`

 - Sign into your 1Password and fly account if you want to use the fly integration.

### Instalation

`pip install 1password-secrets`

## Usage

### Local

To use 1password-secrets locally, you will need to run it from a directory containing your git repository.
Make sure you have a Secure Note in 1Password with `repo:<repository-name>` in the title. `repository-name` is the name of the git repository (ex: `significa/1password-secrets`). You can specify the env file name in 1Password, by adding a text field with the title `file_name` and the value of the file name wanted (ex: `dev.env`). The default file name is `.env`.

To get secrets from 1Password, run:
`1password-secrets local get`

To push the local changes to 1Password, run:
`1password-secrets local push`

### Fly

Make sure you have a Secure Note in 1Password with `fly:<fly-app-name>` in the title. `fly-app-name` is the name of your fly application.

To import secrets to fly, run:
`1password-secrets fly import <fly-app-name>`

Secrets can be edit directly on 1Password app or using the command:
`1password-secrets fly edit <fly-app-name>`
