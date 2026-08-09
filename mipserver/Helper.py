"""Everything the HTTP layer delegates to: git checkouts, compilation, hashing.

The module has two halves:

* Free functions for hashing, copying and JSON pretty-printing.
* :class:`MIPServerHelper`, which owns the cache layout and turns an upstream
  repository into the content-addressed index the ``mip`` client consumes.

External tools ``git`` and ``mpy-cross`` are located via :func:`shutil.which` and
their absence is reported as a failed return value rather than an exception, so a
missing tool degrades into an HTTP error instead of a traceback.
"""

import datetime
import hashlib
import json
import shutil
import subprocess
import traceback
import uuid
from os import stat_result
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from loguru import logger

from mipserver.datastructures.datatypes import JSONObject, JSONValue, MPYPath
from mipserver.datastructures.models import (
    MIPServerFile,
    MIPServerFileL,
    MIPServerPackageJson,
    MIPSRCPackageJson,
    MIPSRCPackageURLEntry,
)


def get_sha256_hash(srcfile: Path) -> str:
    """Compute the sha256 digest of a file, reading it in chunks.

    Args:
        srcfile: The file to hash.

    Returns:
        The hex-encoded digest.

    Raises:
        Exception: If ``srcfile`` does not exist or is not a regular file.
    """
    buf_size: int = 65_536

    if not srcfile.exists():
        raise Exception(f"File does not exist: {srcfile.resolve().absolute()}")

    if not srcfile.is_file():
        raise Exception(f"File does not denote a regular file: {srcfile.resolve().absolute()}")

    sha256 = hashlib.sha256()

    with open(srcfile, "rb") as f:
        while True:
            data: bytes = f.read(buf_size)
            if not data:
                break
            sha256.update(data)

    ret: str = sha256.hexdigest()
    logger.debug(f"SHA256({srcfile.resolve().absolute()}): {ret}")
    return ret


def copy_file(srcfile: Path, tgtfile: Path) -> None:
    """Copy a file chunk-wise.

    The parent directory of ``tgtfile`` has to exist already.

    Args:
        srcfile: Source file.
        tgtfile: Destination path; overwritten if it exists.

    Raises:
        Exception: If ``srcfile`` does not exist or is not a regular file.
    """
    buf_size: int = 65_536

    if not srcfile.exists():
        raise Exception(f"File does not exist: {srcfile.resolve().absolute()}")

    if not srcfile.is_file():
        raise Exception(f"File does not denote a regular file: {srcfile.resolve().absolute()}")

    with open(srcfile, "rb") as fin:
        with open(tgtfile, "wb") as fout:
            while True:
                data: bytes = fin.read(buf_size)
                if not data:
                    break
                fout.write(data)


class ComplexEncoder(json.JSONEncoder):
    """JSON encoder that also handles the non-JSON types showing up in log payloads.

    Understands objects exposing ``repr_json()`` or ``as_string()``, plus
    :class:`uuid.UUID` and the :mod:`datetime` types.
    """

    def default(self, obj: object) -> object:
        """Encode a value :mod:`json` cannot serialize on its own.

        Args:
            obj: The value the encoder stumbled over.

        Returns:
            A JSON-serializable stand-in for ``obj``.

        Raises:
            TypeError: If ``obj`` is of an unsupported type, raised by the base class.
        """
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


def print_pretty_dict_json(data: object, indent: int = 4) -> None:
    """Log ``data`` as indented, key-sorted JSON at INFO level.

    Args:
        data: Any value :class:`ComplexEncoder` can serialize.
        indent: Number of spaces per indentation level.
    """
    from loguru import logger

    logger.info(json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str))


def get_pretty_dict_json(data: object, indent: int = 4) -> str:
    """Render ``data`` as indented, key-sorted JSON.

    Args:
        data: Any value :class:`ComplexEncoder` can serialize.
        indent: Number of spaces per indentation level.

    Returns:
        The formatted JSON document.
    """
    return json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str)


def get_pretty_dict_json_no_sort(data: object, indent: int = 4) -> str:
    """Render ``data`` as indented JSON, preserving insertion order.

    Args:
        data: Any value :class:`ComplexEncoder` can serialize.
        indent: Number of spaces per indentation level.

    Returns:
        The formatted JSON document.
    """
    return json.dumps(data, indent=indent, sort_keys=False, cls=ComplexEncoder, default=str)


def update_deep(
    base: Union[Dict[str, JSONValue], List[JSONValue]],
    u: Union[Dict[str, JSONValue], List[JSONValue]],
) -> Union[Dict[str, JSONValue], List[JSONValue]]:
    """Recursively merge ``u`` into ``base``.

    Lists are merged element-wise and truncated or padded so that ``base`` ends up
    with exactly the length of ``u``. Where the two sides disagree on container
    kind, ``base`` is replaced by an empty container of ``u``'s kind, which discards
    the data previously held there.

    Args:
        base: Structure to merge into. Modified in place where possible.
        u: Structure supplying the new values.

    Returns:
        The merged structure. Not necessarily the same object as ``base``.
    """
    if isinstance(u, dict):
        if not isinstance(base, dict):
            base = {}

        for k, v in u.items():
            if isinstance(v, dict) or isinstance(v, list):
                base[k] = update_deep(base.get(k, {}), v)  # type: ignore[arg-type]
            else:
                base[k] = v

    elif isinstance(u, list):
        if not isinstance(base, list):
            base = []  # may destroy the existing data if mismatch!!!

        # make sure base is long enough
        # could be written more compactly, but this reads well
        while len(base) < len(u):
            base.append(None)

        # make sure base is not longer than needed...
        # could be written more compactly, but this reads well
        while len(base) > len(u):
            base.pop()

        for i, v in enumerate(u):
            if isinstance(v, dict) or isinstance(v, list):
                base[i] = update_deep(base[i] if base[i] is not None else ({} if isinstance(v, dict) else []), v)  # type: ignore[arg-type]
            else:
                base[i] = v

    return base


def get_exception_tb_as_string(exc: Exception) -> str:
    """Format an exception including its traceback.

    Args:
        exc: The exception to format.

    Returns:
        The formatted traceback, one newline-prefixed line per frame.
    """
    tb1: traceback.TracebackException = traceback.TracebackException.from_exception(exc)
    tbsg = tb1.format()
    tbs = ""

    for line in tbsg:
        tbs = tbs + "\n" + line

    return tbs


class MIPServerHelper:
    """Maps package names to GitHub repositories and materializes them in the cache.

    The cache below ``server_cache_root`` is laid out as::

        <root>/<repostem>@<branch>/        # git working tree
        <root>/files/<hh>/<sha256>         # content-addressed blobs
        <root>/<mpy_version>/<package>/<pversion>.json   # generated index

    Instances are cheap and created per request; all state lives on disk.

    Attributes:
        GITHUB_REPO_URL_BASE: Base URL used to build clone URLs.
        GITHUB_DEFAULT_BRANCH: Branch used when the caller does not specify one.
        GITHUB_RAW_BASE: Base URL for the raw-download fallback.
    """

    logger = logger.bind(classname=__qualname__)

    GITHUB_REPO_URL_BASE = "https://github.com"  # /micropython/micropython-lib.git"
    GITHUB_DEFAULT_BRANCH = "main"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com"  # /micropython/micropython-lib/refs/heads/master/"

    def __init__(self, server_cache_root: Path, package_name_to_repo: Dict[str, str]) -> None:
        """Bind the helper to a cache directory and a package mapping.

        Args:
            server_cache_root: Root of the on-disk cache.
            package_name_to_repo: Maps a package name as requested by ``mip`` to an
                ``owner/repo`` GitHub identifier.
        """
        self.server_cache_root = server_cache_root
        self.package_name_to_repo = package_name_to_repo

        self.logger.debug(f"MIPServerHelper::__init__::{server_cache_root=} {package_name_to_repo=}")

    def get_server_cache_root(self) -> Path:
        """Return the root directory of the on-disk cache.

        Returns:
            The cache root this instance was constructed with.
        """
        # Use repository root as server-root as per issue description
        return self.server_cache_root

    def get_local_path_for(self, file_path: Union[str, Path]) -> Path:
        """Resolve a cache-relative path to an absolute one.

        Args:
            file_path: Path relative to the cache root. A leading ``/`` is stripped.

        Returns:
            The absolute path inside the cache.
        """
        p = self.get_server_cache_root() / Path(str(file_path)).as_posix().lstrip("/")
        return p

    def get_local_path_for_package_json_by_package_and_version(
        self, mpy_version: str, package_name: str, pversion: str
    ) -> Path:
        """Build the cache path of a generated package index.

        Args:
            mpy_version: ``"py"`` or the mpy format version, e.g. ``"6"``.
            package_name: Package name as requested by ``mip``.
            pversion: Requested version, which is really a git branch;
                ``"latest"`` stands for the default branch.

        Returns:
            Absolute path of the index json, which need not exist yet.
        """
        rel: str = f"{mpy_version}/{package_name}/{pversion}.json"
        p = self.get_local_path_for(rel)
        return p

    def get_reponame_by_packagename(self, package_name: str) -> Optional[str]:
        """Look up the GitHub repository serving a package.

        Args:
            package_name: Package name as requested by ``mip``.

        Returns:
            The ``owner/repo`` identifier, or ``None`` if the package is not mapped.
        """
        return self.package_name_to_repo.get(package_name)

    @staticmethod
    def generate_package_json_from_local_repo(
        gitrepopath: Path, target_pkgjson: Path, mpy_version: MPYPath = MPYPath.six
    ) -> Path:
        """Turn a checked-out repository into a package index and write it out.

        For every entry of the repository's own ``package.json``: cross-compile the
        source to ``.mpy`` when bytecode was requested, hash the resulting file, copy
        it into the content-addressed store and record the ``[path, hash]`` pair.
        Entries pointing outside the repository are skipped.

        Args:
            gitrepopath: Working tree of the checked-out repository.
            target_pkgjson: Where to write the generated index. Parent directories
                are created as needed.
            mpy_version: ``MPYPath.py`` to ship sources, anything else to ship
                cross-compiled bytecode.

        Returns:
            ``target_pkgjson``.

        Raises:
            AssertionError: If the repository or its ``package.json`` is missing.
            Exception: If ``mpy-cross`` fails for one of the entries.
        """
        src_pkgjson: Path = Path(gitrepopath, "package.json")
        assert gitrepopath.exists() and gitrepopath.is_dir() and src_pkgjson.exists()

        srcdata: JSONObject
        with open(src_pkgjson, "r") as fin:
            srcdata = json.load(fin)

        mr: MIPSRCPackageJson = MIPSRCPackageJson(**srcdata)  # type: ignore[arg-type]

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
                return_target = src_from[:-2] + "mpy"
                return_file = Path(src_from_file.parent, src_from_file.stem + ".mpy")
                # return_file = Path(target_pkgjson.parent, src_from_file.stem + ".mpy")

                logger.debug(f"Compile on the fly from {src_from_file.absolute()} to {return_file.absolute()}")
                logger.debug(f"\tsetting {src_from=} to {return_target=}")

                compile_ok: bool = MIPServerHelper.compile_mpy(
                    py_path=src_from_file, mpy_out=return_file, py_src_name=src_from
                )

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

            msf: MIPServerFile = MIPServerFile(path=return_target, hash=myhash, size=mysize)
            myfiles.append(msf)

            msfl: MIPServerFileL = MIPServerFileL(path=return_target, hash=myhash)
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
    def download_from_github(repo_name: str, raw_rel_path: str) -> Optional[bytes]:
        """Fetch a single file over raw HTTP instead of via git.

        Args:
            repo_name: ``owner/repo`` identifier.
            raw_rel_path: Path inside the repository, including the ``refs/heads/...``
                prefix that ``raw.githubusercontent.com`` expects.

        Returns:
            The file contents, or ``None`` if the request failed or was not answered
            with HTTP 200.
        """
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
        """Cross-compile a Python source file to MicroPython bytecode.

        Runs ``mpy-cross -O2``; a missing binary is reported as failure rather than
        raised. Parent directories of ``mpy_out`` are created as needed.

        Args:
            py_path: Source file to compile.
            mpy_out: Where to write the ``.mpy`` output.
            py_src_name: Source name embedded into the bytecode via ``-s``; should be
                the path the file has on the device.

        Returns:
            ``True`` on success, ``False`` if ``mpy-cross`` is missing, fails or times out.
        """
        mpy_cross = shutil.which("mpy-cross") or shutil.which("mpy-cross-static")
        if not mpy_cross:
            logger.error("mpy-cross not found in PATH")
            return False

        mpy_out.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Basic compile, optimization level 2
            cmd = [mpy_cross, "-O2", str(py_path), "-o", str(mpy_out), "-s", py_src_name]
            logger.debug(f"compile_mpy::{cmd=}")
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                logger.error(f"mpy-cross failed: rc={res.returncode} stderr={res.stderr}")
                return False
            return True
        except Exception as e:
            logger.opt(exception=e).error("mpy-cross execution error")
            return False

    def ensure_files_in_structure_from_repo(
        self, repo_name: str, branch: str = GITHUB_DEFAULT_BRANCH
    ) -> Optional[Path]:
        """Not implemented.

        Args:
            repo_name: ``owner/repo`` identifier.
            branch: Branch to work on.

        Returns:
            Always ``None``; the body is a stub.
        """
        ...

        # 1.

    def ensure_git_repo_up_to_date(self, repo_name: str, branch: str = GITHUB_DEFAULT_BRANCH) -> Optional[Path]:
        """Ensure a local checkout of repo_url@branch exists and is up to date.

        Clones shallowly on first use, otherwise fetches and hard-resets onto the
        remote branch, so local modifications are discarded by design.

        Args:
            repo_name: ``owner/repo`` identifier. Must be one of the mapped repositories.
            branch: Branch to check out. ``"latest"`` is translated to ``"main"``;
                slashes are stripped to prevent path traversal.

        Returns:
            The path to the working tree, or None on failure.

        Raises:
            AssertionError: If ``repo_name`` is not part of the configured mapping.
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
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
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

    def ensure_local_file(
        self,
        repo_name: str,
        raw_rel_path: str,
        branch: str = GITHUB_DEFAULT_BRANCH,
        allow_https_download_fallback: bool = False,
    ) -> Optional[Path]:
        """Ensure a file relative to repository root exists locally under server-root.

        Try to source it from a cached git checkout (updated via clone/pull). If that fails
        or the path doesn't exist in the repo, fall back to a raw HTTP download.

        Args:
            repo_name: ``owner/repo`` identifier.
            raw_rel_path: Path inside the repository; also the path used inside the cache.
            branch: Branch to source the file from. ``"latest"`` means ``"main"``.
            allow_https_download_fallback: Whether to try the raw HTTP download when
                the git checkout does not yield the file.

        Returns:
            Path to the cached file, or ``None`` if it could not be obtained.
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
