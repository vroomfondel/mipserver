#!/bin/bash

cd "$(dirname "$0")" || exit 123

podman run --network=host --userns=keep-id:uid=1200,gid=1201 -it --rm --name mipserverephemeral -p 18891:18891 -v $(pwd)/mipserver/config.local.yaml:/app/mipserver/config.local.yaml -v $(pwd)/.cache:/app/.cache xomoxcc/mipserver:latest
