import os
from contextlib import asynccontextmanager, contextmanager

from os import stat_result
from pathlib import Path
from typing import Annotated, List, Any, Dict, Union, AsyncGenerator, Generator, Optional

from mipserver.config import settings

import datetime
from fastapi import FastAPI, Header, Query, Body, Depends
# fastapi. used here is only a wrapper to starlette.
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

from fastapi.background import BackgroundTasks
from fastapi.datastructures import Headers

from fastapi.requests import Request
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi import Response

from fastapi import FastAPI, Path as FPath, Query

from starlette.exceptions import HTTPException as StarletteHTTPException

from loguru import logger

from mipserver import Helper
from mipserver.Helper import MIPServerHelper
from mipserver.datastructures.datatypes import SensorType, MPYPath
from mipserver.datastructures.models import MIPServerPackageJson, MIPServerFile, ErrorResponse

# Defaults for upstream repository that hosts MicroPython packages
GITHUB_REPO_URL_BASE = "https://github.com"  # /micropython/micropython-lib.git"
GITHUB_DEFAULT_BRANCH = "main"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"  # /micropython/micropython-lib/refs/heads/master/"

SERVER_CACHE_ROOT: Path = Path(os.getcwd(), ".cache") / "repos"
SERVER_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

# git@github.com:vroomfondel/micropysensorbase.git
# https://github.com/vroomfondel/micropysensorbase.git

def error_response(error_msg: str, status_code: int = 500) -> JSONResponse:
    """Helper um ErrorResponse Models als JSONResponse zurückzugeben"""
    error = ErrorResponse(error=error_msg)
    return JSONResponse(content=error.model_dump(), status_code=status_code)

PACKAGE_NAME_TO_REPO: Dict[str, str] = {
    # "micropysensorbase": "vroomfondel/micropysensorbase"
    png.packagename: png.githubrepo for png in settings.packagename_to_github_repo.root
}

def get_package_name_to_repo() -> Dict[str, str]:
    """Dependency function to inject package_name_to_repo dictionary"""
    logger.debug("app::get_package_name_to_repo")
    return PACKAGE_NAME_TO_REPO

# from .datastructures.models import Sensor, Location


__app_description = """
ChimichangApp API helps you do awesome stuff. 🚀

## Items

You can **read items**.

## Users

You will be able to:

* **Create users** (_not implemented_).
* **Read users** (_not implemented_).
"""

__app_tags_metadata: List[dict[str, Any]] | None = [
    {
        "name": "event",
        "description": "Operations with users. The **login** logic is also here.",
    },
    {
        "name": "items",
        "description": "Manage items. So _fancy_ they have their own docs.",
        "externalDocs": {
            "description": "Items external docs",
            "url": "https://fastapi.tiangolo.com/",
        },
    },
]

# from fastapi.responses import ORJSONResponse
# app = FastAPI(default_response_class=ORJSONResponse)
@contextmanager
def mylifespan_sync(_app: FastAPI) -> Generator[None, None]:
    # TODO preload defined packages from github...
    title: str = getattr(_app, "title", "UnknownApp")
    # _app.title  # gives mypy goosebumps. ANNOYING!!!!
    logger.debug(f"{title}::mylifespan::BEFORE yield...")
    yield
    # TODO cleanup
    logger.debug(f"{title}::mylifespan::AFTER yield -> cleanup...")

@asynccontextmanager
async def mylifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Async wrapper für den synchronen Context-Manager"""
    # also, mypy does not know, FastAPI can also digest sync-contextmanager... BLARGH!
    with mylifespan_sync(_app):
        yield

app = FastAPI(
    lifespan=mylifespan,
    title="ChimichangApp",
    description=__app_description,
    version="0.0.1",
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "Deadpoolio the Amazing",
        "url": "http://x-force.example.com/contact/",
        "email": "dp@x-force.example.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    openapi_tags=__app_tags_metadata,

)

# @app.exception_handler(RequestValidationError)
# async def validation_exception_handler(request, exc):
#     print(f"OMG! The client sent invalid data!: {exc}")
#     return await request_validation_exception_handler(request, exc)

def is_in_cluster() -> bool:
    sa: Path = Path("/var/run/secrets/kubernetes.io/serviceaccount")
    if sa.exists() and sa.is_dir():
        return os.getenv("KUBERNETES_SERVICE_HOST") is not None
    return False

@app.get("/")
async def root() -> Dict:
    return {"message": "Hello World"}

def do_request_log(request: Request, **kwargs: Optional[Any]) -> Dict:
    hs: Headers = request.headers
    request_url = str(request.url)

    # Port explizit auslesen
    port = request.url.port
    hostname = request.url.hostname
    scheme = request.url.scheme
    # Vollständige URL mit Port
    request_url_with_port = f"{scheme}://{hostname}:{port}{request.url.path}"
    if request.url.query:
        request_url_with_port += f"?{request.url.query}"


    path: str = request.url.path
    assert request.client is not None, "request.client is None and that is not allowed here..."
    remote_ip: str = request.client.host
    heads: dict = {}

    if kwargs:
        if "file_path" in kwargs:
            file_path = kwargs["file_path"]
            # logger.debug(f"{type(file_path)=} {file_path=}")

    for hk in hs.keys():
        # logger.debug(f"RequestHeader[{hk}]: {hs.get(hk)}")
        heads[hk] = hs.get(hk)

    # logger.debug(f"request.url = {request.url}")
    # logger.debug(f"request.url.port = {request.url.port}")
    # logger.debug(f"request.url.hostname = {request.url.hostname}")
    # logger.debug(f"request.url.scheme = {request.url.scheme}")
    # logger.debug(f"request.url.netloc = {request.url.netloc}")
    # logger.debug(f"Host header = {hs.get('host')}")

    # Hole Port aus ASGI Scope
    server_info = request.scope.get('server')

    # logger.debug(f"request.scope = {server_info}")

    server_host = None
    server_port = None
    full_url = None

    if server_info:
        server_host, server_port = server_info
        logger.debug(f"Server aus Scope: {server_host}:{server_port}")

    # Baue URL mit korrektem Port
    scheme = request.url.scheme
    hostname = request.url.hostname or server_host if server_info else 'localhost'
    port = request.url.port or server_port

    if port:
        full_url = f"{scheme}://{hostname}:{port}{path}"
    else:
        full_url = f"{scheme}://{hostname}{path}"

    if request.url.query:
        full_url += f"?{request.url.query}"

    ret: dict = {
        "remote_ip": remote_ip,
        "headers": heads,
        "request_url": request_url,
        "request_path": path,
        "request_url_full": full_url,
        "url_components": {
            "port": request.url.port,
            "hostname": request.url.hostname,
            "netloc": request.url.netloc,
            "scheme": request.url.scheme,
            },
        "server_scope": request.scope.get('server'),
    }

    return ret


@app.get('/echo')
async def echo(request: Request) -> Dict:
    logger.debug("RECEIVED REQUEST")

    query_params: Dict[str, str] = dict(request.query_params)

    ret: Dict = do_request_log(request, **query_params)

    ret["query_params"] = query_params

    logger.debug(Helper.get_pretty_dict_json_no_sort(ret))
    return ret

# package = "{}/package/{}/{}/{}.json".format(index, mpy_version, package, version)
# return _install_json(package, index, target, version, mpy)



@app.get("/package/{mpy_version:str}/{package_name:str}/{pversion}.json",
         response_model=MIPServerPackageJson,
         responses={500: {"model": ErrorResponse}}
         )
async def get_package_json(mpy_version: Annotated[MPYPath, FPath(...)],
                           package_name: Annotated[str, FPath(..., min_length=3, max_length=100)],
                           pversion: Annotated[str, FPath(..., min_length=3, max_length=64)],
                           package_name_to_repo: Annotated[Dict[str, str], Depends(get_package_name_to_repo)],
                           request: Request) -> MIPServerPackageJson | Response:

    ret: Dict = do_request_log(request, package_name=package_name, mpy_version=mpy_version.value, pversion=pversion)
    # logger.debug(Helper.get_pretty_dict_json_no_sort(ret))

    # mpy_version: "py" or mpy-file-version (.e.g. "6")
    # pversion: "latest" or "1.5.0" or whatever -> this actually means the branch and not a tag/version on the main/master-branch; in case of "latest", it is the main branch

    # This endpoint serves files for MicroPython's mip client.
    # Behavior:
    # - If requested file is not present under server root, try downloading from GitHub
    # - If .mpy is requested, compile from corresponding .py on the fly using mpy-cross
    # - If a .json is requested and not present, generate a simple packages listing JSON

    for k, v in package_name_to_repo.items():
        logger.debug(f"{k=} => {v=}")

    msh: MIPServerHelper = MIPServerHelper(server_cache_root=SERVER_CACHE_ROOT, package_name_to_repo=package_name_to_repo)

    reponame: str|None = msh.get_reponame_by_packagename(package_name)
    if not reponame:
        return error_response("cannot generate package -> invalid packagename")


    logger.debug(f"MIP::get_package_json request for \"/package/{mpy_version}/{package_name}/{pversion}.json\"")

    # JSON handling
    local_json = msh.get_local_path_for_package_json_by_package_and_version(mpy_version=mpy_version, package_name=package_name, pversion=pversion)

    thirty_minutes_ago: datetime.datetime = datetime.datetime.now() - datetime.timedelta(minutes=30)

    if local_json.exists():
        lms: stat_result = local_json.stat()

        if lms.st_ctime >= thirty_minutes_ago.timestamp():
            logger.debug(f"\tReturning {local_json=} from {datetime.datetime.fromtimestamp(lms.st_ctime, settings.timezone)}")
            return FileResponse(local_json, media_type="application/json")

    logger.debug(f"Have to check for updates on git...")
    gitrepopath: Path|None = msh.ensure_git_repo_up_to_date(repo_name=reponame, branch=pversion)  # pversion sollte meist "latest" sein

    if not gitrepopath:
        return error_response("cannot generate package -> git pull failed")

    logger.debug(f"Trying to generate package_json from locally existing github...")
    local_json = msh.generate_package_json_from_local_repo(gitrepopath=gitrepopath, target_pkgjson=local_json, mpy_version=mpy_version)
    if local_json.exists():
        logger.debug(f"\tReturning freshly created {local_json=}")
        return FileResponse(local_json, media_type="application/json")

    return error_response("cannot generate package")


# file_url = "{}/file/{}/{}".format(index, short_hash[:2], short_hash)
@app.get("/file/{short_hash_2:str}/{short_hash:str}")
async def get_file(request: Request,
    short_hash_2: Annotated[str, FPath(..., min_length=2, max_length=2)], # pattern="^[a-fA-F0-9]{2}$"),
    short_hash:  Annotated[str, FPath(..., min_length=64, max_length=64)],
    package_name_to_repo: Annotated[Dict[str, str], Depends(get_package_name_to_repo)]) -> Response:

    ret: Dict = do_request_log(request, short_hash_2=short_hash_2, short_hash=short_hash)

    assert short_hash_2 == short_hash[:2]

    # logger.debug(Helper.get_pretty_dict_json_no_sort(ret))

    msh: MIPServerHelper = MIPServerHelper(server_cache_root=SERVER_CACHE_ROOT,
                                           package_name_to_repo=package_name_to_repo)

    rel = f"files/{short_hash_2}/{short_hash}"

    retfile: Path|None = msh.get_local_path_for(rel)

    if not retfile:
        return error_response(f"File error (not pathable): {rel}")

    if not (retfile.exists() and retfile.is_file()):
        return error_response(f"File not found {rel}")

    mime: str = "application/octet-stream"

    return FileResponse(retfile, media_type=mime)


@app.get("/{whatever:path}")
async def whatever(whatever: Annotated[str, FPath(...)], request: Request) -> Response:
    logger.debug("WHATEVER")
    ret: Dict = do_request_log(request, whatever=whatever)

    logger.debug(Helper.get_pretty_dict_json_no_sort(ret))

    return error_response("UNKNOWN")
