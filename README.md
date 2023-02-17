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

 - Sign into your fly account and 1Password

### Instalation

`pip install 1password-secrets`

## Usage

Make sure you have a Secure Note in 1Password with `fly:<fly-app-name>` in the title. `fly-app-name` is the name of your fly application.

Run:
`1password-secrets fly import <app-name>`
