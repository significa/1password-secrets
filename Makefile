help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-21s\033[0m %s\n", $$1, $$2}'

lint: ## Lint the code according to the standards
	ruff check .
	ruff format --check .
	pyright .

format: ## Format the code according to the standards
	ruff check --fix .
	ruff format .

local-install: ## Install this package with pipx linked to this source code directory
	pipx install --editable .

uninstall: ## Uninstall this package from pipx (regardless of how it was installed)
	pipx uninstall 1password-secrets

install-deps: ## Install python dependencies
	pip install -r requirements.dev.txt

setup-venv: ## Setup a local venv
	python3 -m venv venv
	# Don't forget to activate your env. For example, for bash run: `source ./venv/bin/activate`
