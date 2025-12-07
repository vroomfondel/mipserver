import datetime
import json
import os
import shutil
import subprocess
import traceback
import uuid
from enum import Enum
from os import stat_result
from pathlib import Path
from typing import Any, Dict, List, Union, Literal

import hashlib


import requests
from loguru import logger

from mipserver.datastructures.datatypes import MPYPath
from mipserver.datastructures.models import MIPServerFile, MIPServerPackageJson, MIPSRCPackageJson, \
    MIPSRCPackageURLEntry, MIPServerFileL


def get_sha256_hash(srcfile: Path) -> str:
    buf_size: int = 65_536

    if not srcfile.exists():
        raise Exception(f"File does not exist: {srcfile.resolve().absolute()}")

    if not srcfile.is_file():
        raise Exception(f"File does not denote a regular file: {srcfile.resolve().absolute()}")


    sha256 = hashlib.sha256()

    with open(srcfile, 'rb') as f:
        while True:
            data: bytes = f.read(buf_size)
            if not data:
                break
            sha256.update(data)

    ret: str = sha256.hexdigest()
    logger.debug(f"SHA256({srcfile.resolve().absolute()}): {ret}")
    return ret

def copy_file(srcfile: Path, tgtfile: Path) -> None:
    buf_size: int = 65_536

    if not srcfile.exists():
        raise Exception(f"File does not exist: {srcfile.resolve().absolute()}")

    if not srcfile.is_file():
        raise Exception(f"File does not denote a regular file: {srcfile.resolve().absolute()}")

    with open(srcfile, 'rb') as fin:
        with open(tgtfile, "wb") as fout:
            while True:
                data: bytes = fin.read(buf_size)
                if not data:
                    break
                fout.write(data)




class ComplexEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if hasattr(obj, "repr_json"):
            return obj.repr_json()
        elif hasattr(obj, "as_string"):
            return obj.as_string()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()  # strftime("%Y-%m-%d %H:%M:%S %Z")
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, datetime.timedelta):
            return str(obj)
        elif isinstance(obj, dict) or isinstance(obj, list):
            robj: str = get_pretty_dict_json_no_sort(obj)
            return robj
        else:
            return json.JSONEncoder.default(self, obj)


def print_pretty_dict_json(data: Any, indent: int = 4) -> None:
    from loguru import logger

    logger.info(json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str))


def get_pretty_dict_json(data: Any, indent: int = 4) -> str:
    return json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str)


def get_pretty_dict_json_no_sort(data: Any, indent: int = 4) -> str:
    return json.dumps(data, indent=indent, sort_keys=False, cls=ComplexEncoder, default=str)


def update_deep(base: Dict[str, Any] | List[Any], u: Dict[str, Any] | List[Any]) -> Dict[str, Any] | List[Any]:
    if isinstance(u, dict):
        if not isinstance(base, dict):
            base = {}

        for k, v in u.items():
            if isinstance(v, dict) or isinstance(v, list):
                base[k] = update_deep(base.get(k, {}), v)
            else:
                base[k] = v

    elif isinstance(u, list):
        if not isinstance(base, list):
            base = []  # may destroy the existing data if mismatch!!!

        # Stelle sicher, dass base lang genug ist
        # geht auch kompakter, aber so ist es gut lesbar
        while len(base) < len(u):
            base.append(None)

        # Stelle sicher, dass base nicht länger ist...
        # geht auch kompakter, aber so ist es gut lesbar
        while len(base) > len(u):
            base.pop()

        for i, v in enumerate(u):
            if isinstance(v, dict) or isinstance(v, list):
                base[i] = update_deep(base[i] if base[i] is not None else ({} if isinstance(v, dict) else []), v)  # type: ignore
            else:
                base[i] = v

    return base


def get_exception_tb_as_string(exc: Exception) -> str:
    tb1: traceback.TracebackException = traceback.TracebackException.from_exception(exc)
    tbsg = tb1.format()
    tbs = ""

    for line in tbsg:
        tbs = tbs + "\n" + line

    return tbs

class MIPServerHelper:
    logger = logger.bind(classname=__qualname__)

    GITHUB_REPO_URL_BASE = "https://github.com"  # /micropython/micropython-lib.git"
    GITHUB_DEFAULT_BRANCH = "main"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com"  # /micropython/micropython-lib/refs/heads/master/"

    def __init__(self, server_cache_root: Path, package_name_to_repo: Dict[str, str]):
        self.server_cache_root = server_cache_root
        self.package_name_to_repo = package_name_to_repo

        self.logger.debug(f"MIPServerHelper::__init__::{server_cache_root=} {package_name_to_repo=}")

    def get_server_cache_root(self) -> Path:
        # Use repository root as server-root as per issue description
        return self.server_cache_root


    def get_local_path_for(self, file_path: Union[str, Path]) -> Path:
        p = self.get_server_cache_root() / Path(str(file_path)).as_posix().lstrip('/')
        return p

    def get_local_path_for_package_json_by_package_and_version(self, mpy_version: str, package_name: str, pversion: str) -> Path:
        rel: str = f"{mpy_version}/{package_name}/{pversion}.json"
        p = self.get_local_path_for(rel)
        return p


    def get_reponame_by_packagename(self, package_name: str) -> str|None:
        return self.package_name_to_repo.get(package_name)


    @staticmethod
    def generate_package_json_from_local_repo(gitrepopath: Path, target_pkgjson: Path, mpy_version: MPYPath = MPYPath.six) -> Path:
        src_pkgjson: Path = Path(gitrepopath, "package.json")
        assert gitrepopath.exists() and gitrepopath.is_dir() and  src_pkgjson.exists()

        srcdata: dict
        with open(src_pkgjson, "r") as fin:
            srcdata = json.load(fin)

        mr: MIPSRCPackageJson = MIPSRCPackageJson(**srcdata)

        # package_version: str = mr.version
        myfiles: List[MIPServerFile] = []
        myhashes: List[MIPServerFileL] = []

        srcu: MIPSRCPackageURLEntry
        for srcu in mr.urls:
            src_from: str = srcu.url_from  # may even be an external url... ?!
            src_target: str = srcu.url_to

            # TODO check if src_from is a local file and that file exist...
            src_from_file: Path = Path(gitrepopath, src_from).resolve()
            return_file: Path = src_from_file
            # return_file: Path = Path(target_pkgjson.parent, src_from_file.name)

            return_target: str = src_target

            if not src_from_file.is_relative_to(gitrepopath):
                logger.debug(f"{src_from=} => {src_from_file=}  ==> not in {gitrepopath=}")
                continue

            if src_from_file.name.endswith(".py") and mpy_version.value != "py":
                return_target = src_from[:-2]+"mpy"
                return_file = Path(src_from_file.parent, src_from_file.stem + ".mpy")
                # return_file = Path(target_pkgjson.parent, src_from_file.stem + ".mpy")

                logger.debug(f"Compile on the fly from {src_from_file.absolute()} to {return_file.absolute()}")
                logger.debug(f"\tsetting {src_from=} to {return_target=}")

                compile_ok: bool = MIPServerHelper.compile_mpy(py_path=src_from_file, mpy_out=return_file, py_src_name=src_from)

                if not compile_ok:
                    raise Exception(f"Compilation from {src_from_file=} to {return_file=}")

                logger.debug(f"Compilation OK for {return_file=}")


            myhash: str = get_sha256_hash(return_file)
            mysize: int = return_file.stat().st_size

            # move into proper file structure...
            return_file_in_index_dir: Path = Path(gitrepopath.parent, "files")
            return_file_in_index_dir = Path(return_file_in_index_dir, myhash[0:2])
            return_file_in_index_dir.mkdir(parents=True, exist_ok=True)
            return_file_in_index_dir = Path(return_file_in_index_dir, myhash)

            copy_file(return_file, return_file_in_index_dir)

            msf: MIPServerFile = MIPServerFile(
                path=return_target,
                hash=myhash,
                size=mysize
            )
            myfiles.append(msf)

            msfl: MIPServerFileL = MIPServerFileL(
                path=return_target,
                hash=myhash
            )
            myhashes.append(msfl)



        # TODO not really nexessary to include "files" here -> there was some "irritating" documentation floating around...
        # mpj: MIPServerPackageJson = MIPServerPackageJson(files=myfiles, hashes=myhashes)
        mpj: MIPServerPackageJson = MIPServerPackageJson(hashes=myhashes)

        target_pkgjson.parent.mkdir(parents=True, exist_ok=True)

        with open(target_pkgjson, "w") as fout:
            fout.write(mpj.model_dump_json(indent=4))

        fstat: stat_result = target_pkgjson.stat()
        logger.debug(f"Written {fstat.st_size} bytes to {target_pkgjson.resolve().absolute()}")

        return target_pkgjson


    @staticmethod
    def download_from_github(repo_name: str, raw_rel_path: str) -> bytes | None:
        """Simple raw HTTP download fallback for a given relative path inside the repo."""
        url = f"{MIPServerHelper.GITHUB_RAW_BASE}/{repo_name}/{raw_rel_path.lstrip('/')}"
        logger.debug(f"Downloading from GitHub: {url}")
        try:
            resp = requests.get(url, timeout=30)
        except Exception as e:
            logger.opt(exception=e).warning("GitHub raw fetch exception")
            return None
        if resp.status_code == 200:
            return resp.content
        logger.warning(f"GitHub fetch failed {resp.status_code} for {url}")
        return None


    @staticmethod
    def compile_mpy(py_path: Path, mpy_out: Path, py_src_name: str) -> bool:
        mpy_cross = shutil.which("mpy-cross") or shutil.which("mpy-cross-static")
        if not mpy_cross:
            logger.error("mpy-cross not found in PATH")
            return False

        mpy_out.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Basic compile, optimization level 2
            cmd = [mpy_cross, "-O2", str(py_path), "-o", str(mpy_out), "-s", py_src_name]
            logger.debug(f"compile_mpy::{cmd=}")
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=120)
            if res.returncode != 0:
                logger.error(f"mpy-cross failed: rc={res.returncode} stderr={res.stderr}")
                return False
            return True
        except Exception as e:
            logger.opt(exception=e).error("mpy-cross execution error")
            return False


    def ensure_files_in_structure_from_repo(self, repo_name: str, branch: str = GITHUB_DEFAULT_BRANCH) -> Path | None:
        ...

        # 1.

    def ensure_git_repo_up_to_date(self, repo_name: str, branch: str = GITHUB_DEFAULT_BRANCH) -> Path | None:
        """Ensure a local checkout of repo_url@branch exists and is up to date.

        Returns the path to the working tree, or None on failure.
        """

        assert repo_name in self.package_name_to_repo.values()

        repo_url: str = f"{MIPServerHelper.GITHUB_REPO_URL_BASE}/{repo_name}.git"

        git_bin = shutil.which("git")
        if not git_bin:
            logger.warning("git not found in PATH; falling back to raw HTTP")
            return None

        cache_root = self.get_server_cache_root()

        branch = branch.replace("/", "")  # cleanup against possible path traversals etc.

        git_branch: str = "main"
        if branch != "latest":
            git_branch = branch

        checkout_dir = cache_root / (Path(repo_url).stem + f"@{branch}")
        logger.debug(f"_ensure_git_repo_up_to_date({repo_name=}, {git_branch=}) {checkout_dir=}")

        try:
            cache_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.opt(exception=e).warning("Failed to create cache directory for git repos")
            return None

        try:
            if not checkout_dir.exists():
                # Clone shallow
                logger.info(f"Cloning {repo_url}@{git_branch} into {checkout_dir}")

                checkout_dir.parent.mkdir(parents=True, exist_ok=True)

                cmd = [git_bin, "clone", "--depth", "1", "--branch", git_branch, repo_url, str(checkout_dir)]
                logger.debug(f"EXEC {cmd}")
                res = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=300
                )
                if res.returncode != 0:
                    logger.error(f"git clone failed: {res.returncode} stderr={res.stderr}")
                    return None
            else:
                # Fetch and reset to the remote branch
                logger.debug(f"Updating repo {checkout_dir}")
                cmds = [
                    [git_bin, "-C", str(checkout_dir), "fetch", "--depth", "1", "origin", git_branch],
                    [git_bin, "-C", str(checkout_dir), "checkout", git_branch],
                    [git_bin, "-C", str(checkout_dir), "reset", "--hard", f"origin/{git_branch}"],
                ]
                for cmd in cmds:
                    logger.debug(f"EXEC: {cmd}")
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if res.returncode != 0:
                        logger.error(f"git command failed: {cmd} rc={res.returncode} stderr={res.stderr}")
                        return None
        except Exception as e:
            logger.opt(exception=e).error("git operations failed")
            return None

        return checkout_dir


    def ensure_local_file(self, repo_name: str,
                           raw_rel_path: str,
                           branch: str = GITHUB_DEFAULT_BRANCH,
                           allow_https_download_fallback: bool = False) -> Path | None:
        """Ensure a file relative to repository root exists locally under server-root.

        Try to source it from a cached git checkout (updated via clone/pull). If that fails
        or the path doesn't exist in the repo, fall back to a raw HTTP download.
        """
        target = self.get_local_path_for(raw_rel_path)

        logger.debug(f"_ensure_local_file({repo_name=}, {raw_rel_path=} {branch=}) {target=}")

        branch = branch.replace("/", "")  # cleanup against possible path traversals etc.
        git_branch: str = "main"
        if branch != "latest":
            git_branch = branch

        if target.exists():
            return target

        # First, try via git checkout
        checkout = self.ensure_git_repo_up_to_date(repo_name=repo_name, branch=branch)
        if checkout is not None:
            repo_file = (checkout / raw_rel_path.lstrip("/")).resolve()
            try:
                repo_file.relative_to(checkout)
            except Exception:
                # Prevent path traversal
                logger.warning("Rejected path outside checkout: %s", raw_rel_path)
                repo_file = None  # type: ignore
            if repo_file and repo_file.exists() and repo_file.is_file():

                target.parent.mkdir(parents=True, exist_ok=True)

                try:
                    content = repo_file.read_bytes()
                    target.write_bytes(content)
                    return target
                except Exception as e:
                    logger.opt(exception=e).warning("Failed to copy file from git checkout; will try HTTP")

        if not allow_https_download_fallback:
            return None
            # raise Exception("NOT FOUND EXCEPTION ")

        # Fallback: raw HTTP download
        http_data = self.download_from_github(repo_name=repo_name, raw_rel_path=raw_rel_path)
        if http_data is None:
            return None

        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            target.write_bytes(http_data)
        except Exception as e:
            logger.opt(exception=e).error("Failed to write downloaded file")
            return None
        return target