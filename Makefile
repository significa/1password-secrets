help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-21s\033[0m %s\n", $$1, $$2}'

lint: ## Ensure code properly formatted
	pycodestyle .
	flake8 .
	isort . --check

format: ## Format the code according to the standards
	autopep8 --recursive --in-place .
	flake8 --format .
	isort .

local-install: ## Link the current directory to the user installation
	pip3 install --force-reinstall --user --editable .

install-deps: ## Install python dependencies
	pip install -r requirements.dev.txt

setup-venv: ## Setup a local venv
	python3 -m venv env