[![mypy and pytests](https://github.com/vroomfondel/mipserver/actions/workflows/mypynpytests.yml/badge.svg)](https://github.com/vroomfondel/mipserver/actions/workflows/mypynpytests.yml)
[![BuildAndPushMultiarch](https://github.com/vroomfondel/mipserver/actions/workflows/buildmultiarchandpush.yml/badge.svg)](https://github.com/vroomfondel/mipserver/actions/workflows/buildmultiarchandpush.yml)
![Cumulative Clones](https://img.shields.io/endpoint?logo=github&url=https://gist.githubusercontent.com/vroomfondel/c2a4e6ab3042d0a3b866de993fc8c896/raw/mipserver_clone_count.json)

[![https://github.com/vroomfondel/mipserver/raw/main/Gemini_Generated_Image_mipserver_5jsu1b5jsu1b5jsu_250x250.png](https://github.com/vroomfondel/mipserver/raw/main/Gemini_Generated_Image_mipserver_5jsu1b5jsu1b5jsu_250x250.png)](https://hub.docker.com/r/xomoxcc/mipserver/tags)

# mipserver

Overview
- mipserver is a lightweight, container-friendly HTTP service that accelerates and stabilizes MicroPython package deployment via mip.
- It acts as a local, cache-aware proxy in front of upstream sources (e.g., GitHub releases, PyPI wheels converted for MicroPython, or other artifact stores) and can optionally perform on-the-fly mpy-cross compilation to deliver architecture-appropriate .mpy artifacts to constrained devices.
- Designed for lab and field deployments, mipserver reduces device-side bandwidth, avoids upstream rate limits, and ensures reproducible installations in environments with intermittent connectivity.

Intended usage and related work
- Typical usage is side-by-side with a MicroPython device fleet, enabling fast, deterministic mip installs during provisioning and updates.
- See also the companion project micropysensorbase for an example of how devices can consume packages served by mipserver:
  https://github.com/vroomfondel/micropysensorbase

Key capabilities
- Local proxy for mip package resolution and downloads with request logging.
- Transparent caching of package indices and artifacts to minimize upstream calls.
- Optional on-the-fly mpy-cross compilation to target-specific .mpy files.
- Simple configuration via YAML with sensible defaults and overrides (config.yaml, config.local.yaml).
- Docker-first deployment, including multi-architecture images.
- Observability-friendly request logging endpoint for troubleshooting.

When to use mipserver
- You maintain multiple MicroPython devices and want to speed up firmware/package updates.
- You need local control over what packages/versions are served to devices.
- Your environment has restricted or unstable internet connectivity and you want a resilient cache.
- You want reproducible, auditable updates independent of upstream rate limits or layout changes.

How it works (high level)
- Devices perform mip operations against mipserver instead of directly hitting upstream sources.
- mipserver resolves package metadata (e.g., package.json) and artifacts, caching them under ./.cache.
- If configured, it compiles source to .mpy using mpy-cross so that devices receive optimized bytecode per target.
- Requests and responses can be inspected via the server’s logging endpoint to aid debugging.

Usage

The project uses Make targets to streamline common tasks. 
Below is a concise guide to the available targets and typical workflows, based on the Makefile.

Prerequisites
- GNU Make
- Docker (for building/running the container)
- Python 3.13 (optional locally; CI skips venv creation)

Conventions
- Many targets activate a local virtualenv automatically unless GITHUB_RUN_ID is set (in CI). The venv lives under .venv/.
- A local configuration file can override defaults: mipserver/config.local.yaml. If it does not exist, some targets will create an empty one.

Core targets
- make help
  Prints a short description of available targets.

- make install
  Creates/updates the local virtual environment and installs development dependencies from requirements-dev.txt.

- make tests
  Runs the test suite via pytest.

- make lint
  Formats the codebase with black (line length 120).

- make isort
  Sorts and organizes imports.

- make tcheck
  Static type checks with mypy for *.py and the mipserver package.

- make commit-checks
  Installs and runs pre-commit hooks across all files.

- make prepare
  Convenience target to run tests and commit-checks.

- make build
  Executes ./build.sh to build the Docker image (multi-arch build configuration present in docker-config/).

- make dstart
  Starts the application in a disposable Docker container mapped to host port 18891 and mounts:
  - ./mipserver/config.local.yaml → /app/mipserver/config.local.yaml
  - ./.cache → /app/.cache
  The target also ensures ./.cache exists and attempts to set ACLs for both host user and container user (1200:1201) so that caches are writable.

Quick start
1) Prepare local environment (optional, for running tools/tests locally):
   - make install
   - make tests
   - make lint
   - make isort
   - make tcheck

2) Build and run with Docker:
   - make build
   - make dstart

Configuration
- Default configuration lives in mipserver/config.yaml.
- To customize without modifying the default, create mipserver/config.local.yaml. Many targets will create an empty file if it does not exist.

Notes
- CI behavior: When GITHUB_RUN_ID is set, venv creation and package installation in install are skipped by design.
- If you want to run the image manually without make, an example (current user mapping variant is commented in Makefile):
  docker run --network=host -it --rm \
    --name mipserverephemeral \
    -p 18891:18891 \
    -v $(pwd)/mipserver/config.local.yaml:/app/mipserver/config.local.yaml \
    -v $(pwd)/.cache:/app/.cache \
    xomoxcc/mipserver:latest

Troubleshooting
- Permission issues with ./.cache in Docker: make dstart attempts to set ACLs on ./.cache for both host and container users. If ACLs are unsupported on your filesystem, adjust permissions manually or run the container with --user $(id -u):$(id -g).

Security considerations
- If exposing mipserver beyond a trusted network, place it behind a reverse proxy with authentication and TLS.
- Review which upstream sources are permitted and pin exact package versions to avoid supply-chain surprises.

Compatibility
- Targeted at MicroPython devices that use mip for package management.
- mpy-cross versions should match the target MicroPython runtime ABI for best compatibility.

## Version History

* -0.42
    * there will be no proper versioning

## License

This project is licensed under the LGPL where applicable/possible License - see the [LICENSE.md](LICENSE.md) file for details.
Some files/part of files could be governed by different/other licenses and/or licensors, 
such as (e.g., but not limited to) [MIT](LICENSEMIT.md) | [GPL](LICENSEGPL.md) | [LGPL](LICENSELGPL.md); so please also 
regard/pay attention to comments in regards to that throughout the codebase / files / part of files.

## Acknowledgments

Inspiration, code snippets, etc.
* please see comments in files for that


## ⚠️ Disclaimer

This is a development/experimental project. For production use, review security settings, customize configurations, and test thoroughly in your environment. Provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software. Use at your own risk.