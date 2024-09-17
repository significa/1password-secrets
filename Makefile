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

local-install: ## Link the current directory to the user installation
	pip3 install --force-reinstall --user --editable .

install-deps: ## Install python dependencies
	pip install -r requirements.dev.txt

setup-venv: ## Setup a local venv
	python3 -m venv venv
