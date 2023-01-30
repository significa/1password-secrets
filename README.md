comments ok 
# fly-1password-secrets

fly-1pasword-secrets is a CLI to sync secrets stored in 1Password with fly applications.

## Requirements

1. 1Password >= `8.9.13` - `brew install --cask 1password`
2. 1Password CLI >=  `2.13.1` - `brew install --cask 1password-cli`
3. flyctl `brew install flyctl`

## Getting started

1. Create a Secure Note in 1Password with `fly.{fly-app-name}` in the title. You should not have multiple Secure Notes with this reference.

2. Allow 1Password to connect to 1Password-CLI by going to `Settings` -> `Developer` -> `Command-Line Interface (CLI)` and select `Connect with 1Password CLI`

3. Sign into your fly account
`flyctl auth login`

## Usage

`fly-1password-secrets {app-name}`
