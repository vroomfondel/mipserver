"""Pydantic models for the wire formats handled by this server.

Two directions are covered:

* **Emitted** by this server towards the ``mip`` client — :class:`MIPServerPackageJson`
  with its :class:`MIPServerFileL` entries, and :class:`ErrorResponse`.
* **Consumed** from an upstream repository — :class:`MIPSRCPackageJson` with its
  :class:`MIPSRCPackageURLEntry` entries, i.e. the ``package.json`` that lives in
  the GitHub repository being served.

Both of the ``mip`` formats use two-element arrays where one would expect an
object. The models keep named fields for readability and bridge the gap with a
``model_serializer`` (outgoing) and a ``model_validator`` (incoming).
"""

from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from mipserver.datastructures.datatypes import SensorType

if TYPE_CHECKING:  # loguru ships `Logger` only in its stubs, not at runtime
    from loguru import Logger


class ErrorResponse(BaseModel):
    """Body returned for every failure of this app.

    Note that the app answers with HTTP 500 for client-side mistakes as well; see
    :func:`mipserver.app.error_response`.

    Attributes:
        error: Human-readable error message.
    """

    error: str


class UrlComponents(BaseModel):
    """The parsed pieces of a request URL.

    Attributes:
        port: Port taken from the URL, if it carried one.
        hostname: Host taken from the URL, if it carried one.
        netloc: Host and port as written in the URL.
        scheme: URL scheme, ``"http"`` or ``"https"``.
    """

    port: Optional[int]
    hostname: Optional[str]
    netloc: str
    scheme: str


class RequestLog(BaseModel):
    """What :func:`mipserver.app.do_request_log` observed about a request.

    Attributes:
        remote_ip: Peer address of the client.
        headers: All request headers; keys are lower-cased by the ASGI server.
        request_url: The URL as seen by the framework.
        request_path: Path component only.
        request_url_full: URL rebuilt from scheme, host, port and query, falling back
            to the ASGI scope when the URL itself carries no host or port.
        url_components: The individual URL pieces.
        server_scope: ``(host, port)`` from the ASGI scope, if the server provided it.
    """

    remote_ip: str
    headers: Dict[str, str]
    request_url: str
    request_path: str
    request_url_full: str
    url_components: UrlComponents
    server_scope: Optional[Tuple[str, Optional[int]]]


class EchoResponse(RequestLog):
    """Body of ``GET /echo``: the request log plus the parsed query string.

    Attributes:
        query_params: Query parameters of the request.
    """

    query_params: Dict[str, str]


class MIPServerFile(BaseModel):
    """A single served file including its size.

    Only used for the optional ``files`` member of the package index, which this
    server currently does not emit; :class:`MIPServerFileL` is what goes on the wire.

    Attributes:
        path: Path as it should be created on the device, e.g. ``"mypackage/__init__.mpy"``.
        hash: Hex-encoded sha256 digest of the file contents.
        size: File size in bytes.
    """

    path: str
    hash: str  # sha256 is there a type for that?!
    size: int


class MIPServerFileL(BaseModel):
    """A ``[path, hash]`` pair as it appears in the ``hashes`` list.

    Attributes:
        path: Path as it should be created on the device.
        hash: Hex-encoded sha256 digest, which is also the key under which the blob
            is reachable via ``GET /file/{hash[:2]}/{hash}``.
    """

    path: str
    hash: str

    @model_serializer
    def serialize_model(self) -> List[str]:
        """Serialize as a two-element array instead of an object.

        This is what the ``mip`` client expects; the named fields exist for
        readability on the Python side only.

        Returns:
            ``[path, hash]``.
        """
        return [self.path, self.hash]


class MIPServerPackageJson(BaseModel):
    """The package index this server returns for ``/package/{mpy}/{name}/{ver}.json``.

    Attributes:
        hashes: The files making up the package, each serialized as ``[path, hash]``.
    """

    # files: List[MIPServerFile]
    hashes: List[MIPServerFileL]


# * using HTTP/2
# * [HTTP/2] [1] OPENED stream for https://micropython.org/pi/v2/file/12/12a36a41
# * [HTTP/2] [1] [:method: GET]
# * [HTTP/2] [1] [:scheme: https]
# * [HTTP/2] [1] [:authority: micropython.org]
# * [HTTP/2] [1] [:path: /pi/v2/file/12/12a36a41]
# * [HTTP/2] [1] [user-agent: curl/8.5.0]
# * [HTTP/2] [1] [accept: */*]
# > GET /pi/v2/file/12/12a36a41 HTTP/2
# > Host: micropython.org
# > User-Agent: curl/8.5.0
# > Accept: */*
# >
# < HTTP/2 200
# < server: nginx
# < date: Sat, 06 Dec 2025 18:14:11 GMT
# < content-type: application/octet-stream
# < content-length: 3144
# < last-modified: Thu, 31 Jul 2025 15:03:16 GMT
# < etag: "688b85b4-c48"
# < access-control-allow-origin: *
# < accept-ranges: bytes
# <
# Warning: Binary output can mess up your terminal. Use "--output -" to tell
# Warning: curl to output it to your terminal anyway, or consider "--output
# Warning: <FILE>" to save to a file.
# * Failure writing output to destination
# * Connection #0 to host micropython.org left intact

# curl -v https://micropython.org/pi/v2/package/6/aiorepl/latest.json
# {"hashes":[["aiorepl.mpy","12a36a41"]],"v":1,"version":"0.2.2"}


# curl -v https://micropython.org/pi/v2/file/12/12a36a41

# class MIPSRCPackageURLEntry(RootModel):
#     root: Annotated[List[str], Field(..., min_length=2, max_length=2)]

# Imported for its side effect, not for its name: importing `config` installs the loguru
# handler whose format string references `extra[classname]`. Keep it ahead of the
# `logger.bind(...)` below, which runs at class definition time.
from mipserver import config  # noqa: F401
from loguru import logger


class MIPSRCPackageURLEntry(BaseModel):
    """One ``urls`` entry of an upstream repository's own ``package.json``.

    Upstream writes these as two-element arrays, ``["<target on device>", "<source in repo>"]``.

    Attributes:
        url_from: First element — the path the file gets on the device.
        url_to: Second element — where the file lives inside the repository.
    """

    url_from: str
    url_to: str

    logger: ClassVar["Logger"] = logger.bind(classname=__qualname__)
    logger.level("INFO")

    @model_validator(mode="before")
    @classmethod
    def _populate_root(cls, v: object) -> object:
        """Accept the upstream two-element array form.

        Args:
            v: Raw input. A ``list`` is the upstream array form and gets mapped onto
                the named fields; anything else is passed through untouched so that
                the ordinary keyword constructor keeps working.

        Returns:
            A ``dict`` with ``url_from``/``url_to`` for list input, otherwise ``v``.

        Raises:
            AssertionError: If a list input does not hold exactly two elements.
        """
        cls.logger.debug(f"_populate_root_::{type(v)=} {v=}")

        if isinstance(v, list):
            assert len(v) == 2
            return {"url_from": v[0], "url_to": v[1]}

        return v


class MIPSRCPackageJson(BaseModel):
    """The ``package.json`` as found in the upstream GitHub repository.

    Attributes:
        version: Version string declared upstream. Recorded but not used for routing —
            the requested ``pversion`` is a git branch, not this value.
        urls: The files the package consists of.
    """

    version: str
    urls: List[MIPSRCPackageURLEntry]


# class KeelMessage(BaseModel):
#     name: str
#     message: str
#     createdAt: datetime
#
#     @field_validator('createdAt')
#     @classmethod
#     def adapt_timezone(cls, v: datetime) -> datetime:
#         return v.astimezone(config._tzberlin)

# {
# 	"name": "update deployment",
# 	"message": "Successfully updated deployment default/wd (karolisr/webhook-demo:0.0.10)",
# 	"createdAt": "2017-07-08T10:08:45.226565869+01:00"
# }


class Sensor(BaseModel):
    """Scaffolding leftover; not referenced by any route.

    Attributes:
        sensor: The sensor family.
    """

    sensor: SensorType


class Item(BaseModel):
    """Scaffolding leftover from the FastAPI tutorial; not referenced by any route.

    Attributes:
        name: Item name.
        price: Item price.
        tax: Optional tax amount.
        tags: Free-form tags.
        description: Optional long description.
    """

    name: str
    price: float
    tax: float | None = None
    tags: List[str] = Field(default_factory=list)
    description: Union[str, None] = Field(default=None, json_schema_extra={"example": "A very nice Item"})

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Foo",
                "description": "A very nice Item",
                "price": 35.4,
                "tax": 3.2,
            }
        }
    )


#
# def fake_save_user(user_in: UserIn):
#     hashed_password = fake_password_hasher(user_in.password)
#     user_in_db = UserInDB(**user_in.dict(), hashed_password=hashed_password)
#     print("User saved! ..not really")
#     return user_in_db


#
# class UserBase(BaseModel):
#     username: str
#     email: EmailStr
#     full_name: Union[str, None] = None
#
#
# class UserIn(UserBase):
#     password: str
#
#
# class UserOut(UserBase):
#     pass
#
#
# class UserInDB(UserBase):
#     hashed_password: str
#
#
# def fake_password_hasher(raw_password: str):
#     return "supersecret" + raw_password
#
#
# def fake_save_user(user_in: UserIn):
#     hashed_password = fake_password_hasher(user_in.password)
#     user_in_db = UserInDB(**user_in.dict(), hashed_password=hashed_password)
#     print("User saved! ..not really")
#     return user_in_db
#
#
# @app.post("/user/", response_model=UserOut)
# async def create_user(user_in: UserIn):
#     user_saved = fake_save_user(user_in)
#     return user_saved
