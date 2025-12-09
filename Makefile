.PHONY: tests help install venv lint dstart isort tcheck build commit-checks prepare
SHELL := /usr/bin/bash
.ONESHELL:

help:
	@printf "\ninstall\n\tinstall requirements\n"
	@printf "\nisort\n\tmake isort import corrections\n"
	@printf "\nlint\n\tmake linter check with black\n"
	@printf "\ntcheck\n\tmake static type checks with mypy\n"
	@printf "\ntests\n\tLaunch tests\n"
	@printf "\nprepare\n\tLaunch tests and commit-checks\n"
	@printf "\ncommit-checks\n\trun pre-commit checks on all files\n"
	# @printf "\nstart \n\tstart app in gunicorn - listening on port 8055\n"
	@printf "\nbuild \n\tbuild docker image\n"
	@printf "\ndstart \n\tlaunch \"app\" in docker\n"

# check for "CI" not in os.environ || "GITHUB_RUN_ID" not in os.environ
venv_activated=if [ -z $${VIRTUAL_ENV+x} ] && [ -z $${GITHUB_RUN_ID+x} ] ; then printf "activating venv...\n" ; source .venv/bin/activate ; else printf "venv already activated or GITHUB_RUN_ID=$${GITHUB_RUN_ID} is set\n"; fi

install: venv

venv: .venv/touchfile

.venv/touchfile: requirements.txt requirements-dev.txt requirements-local.txt
	@if [ -z "$${GITHUB_RUN_ID}" ]; then \
		test -d .venv || python3.14 -m .venv; \
		source .venv/bin/activate; \
		pip install -r requirements-dev.txt; \
		touch .venv/touchfile; \
	else \
  		echo "Skipping venv setup because GITHUB_RUN_ID is set"; \
  	fi


tests: venv
	@$(venv_activated)
	pytest -v .

lint: venv
	@$(venv_activated)
	black -l 120 .

dstart:
	@# map config.local.yaml from current workdirectory into container
	@if ! [ -e .cache ]; then echo creating .cache ; mkdir .cache ; else echo already exists .cache; fi
	@if ! [ -e mipserver/config.local.yaml ] ; then creating empty mipserver/config.local.yaml ; touch mipserver/config.local.yaml ; fi
	@echo "Setting ACLs for host user $$(id -u):$$(id -g)"
	@setfacl -R -m u:$$(id -u):rwx,g:$$(id -g):rwx -d -m u:$$(id -u):rwx,g:$$(id -g):rwx .cache
	@echo "Setting ACLs for container user 1200:1201"
	@setfacl -R -m u:1200:rwx,g:1201:rwx -d -m u:1200:rwx,g:1201:rwx .cache
	docker run --network=host -it --rm --name mipserverephemeral -p 18891:18891 \
		-v $$(pwd)/mipserver/config.local.yaml:/app/mipserver/config.local.yaml \
		-v $$(pwd)/.cache:/app/.cache \
		xomoxcc/mipserver:latest

# or run with current userid
# docker run --user $(id -u):$(id -g) --network=host -it --rm --name mipserverephemeral -p 18891:18891 -v $(pwd)/mipserver/config.local.yaml:/app/mipserver/config.local.yaml -v $(pwd)/.cache:/app/.cache xomoxcc/mipserver:latest

isort: venv
	@$(venv_activated)
	isort .

tcheck: venv
	@$(venv_activated)
	mypy *.py mipserver
	# mypy -v *.py mipserver  2> >(grep "Found source") | sed "s_.*path='\(.*\)py'.*_\1py_"
    # mypy *.py **/*.py

build: venv
	./build.sh

.git/hooks/pre-commit: venv
	@$(venv_activated)
	pre-commit install

commit-checks: .git/hooks/pre-commit
	@$(venv_activated)
	pre-commit run --all-files

prepare: tests commit-checks

#pypibuild: .venv
#	@$(venv_activated)
#	pip install -r requirements-build.txt
#	pip install --upgrade twine build
#	python3 -m build

