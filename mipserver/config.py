"""Settings singleton and logging setup.

Importing this module has two side effects that the rest of the package relies on:

1. **Logging.** The default loguru handler is removed and replaced by a stderr
   handler at ``LOGURU_LEVEL`` (default ``DEBUG``). Its format references
   ``{extra[classname]}``, so every logger must carry that key — classes bind it via
   ``logger.bind(classname=__qualname__)``. Records carrying ``skiplog=True`` are
   dropped by :func:`_loguru_skiplog_filter`.
2. **Settings.** :data:`settings` is constructed at import time. Its required
   sections must be present, so a readable ``config.yaml`` has to exist for the
   import to succeed at all — including under pytest.

Sources are consulted in this order (first wins): init arguments, environment,
YAML. YAML means both ``config.yaml`` and ``config.local.yaml``, the latter taking
precedence; all three paths can be redirected via ``CONFIG_DIR_PATH``,
``CONFIG_PATH`` and ``CONFIG_LOCAL_PATH``. Environment variables nest with ``__``
and are case-insensitive, e.g. ``UVICORN__PORT=8080``.
"""

import datetime

# https://docs.pydantic.dev/latest/concepts/pydantic_settings/

import os
import sys
from enum import StrEnum, auto
from functools import partial
from pathlib import Path
from pprint import pprint

import pytz
from typing import (
    Annotated,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
)

from loguru import logger
from pydantic_core.core_schema import ValidationInfo

os.environ["LOGURU_LEVEL"] = os.getenv("LOGURU_LEVEL", "DEBUG")  # standard is DEBUG
logger.remove()  # remove default-handler

logger_fmt: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>::<cyan>{extra[classname]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
# logger_fmt: str = "<g>{time:HH:mm:ssZZ}</> | <lvl>{level}</> | <c>{module}::{extra[classname]}:{function}:{line}</> - {message}"


def _loguru_skiplog_filter(record: Mapping[str, object]) -> bool:
    """Drop log records that were explicitly marked as to-be-skipped.

    Args:
        record: The loguru record. Suppression is requested by binding
            ``skiplog=True`` on the logger or the record's ``extra`` mapping.

    Returns:
        ``False`` if the record should be suppressed, ``True`` otherwise.
    """
    extra = record.get("extra")
    if not isinstance(extra, Mapping):
        return True

    return not bool(extra.get("skiplog", False))


logger.add(sys.stderr, level=os.getenv("LOGURU_LEVEL"), format=logger_fmt, filter=_loguru_skiplog_filter)  # type: ignore # TRACE | DEBUG | INFO | WARN | ERROR |  FATAL
logger.configure(extra={"classname": "None", "skiplog": False})


_CONFIGDIRPATH: Path = Path(__file__).parent.resolve()
_CONFIGDIRPATH = Path(os.getenv("CONFIG_DIR_PATH", _CONFIGDIRPATH))

_CONFIGPATH: Path = Path(_CONFIGDIRPATH, "config.yaml")
_CONFIGPATH = Path(os.getenv("CONFIG_PATH", _CONFIGPATH))

_CONFIGLOCALPATH: Path = Path(_CONFIGDIRPATH, "config.local.yaml")
_CONFIGLOCALPATH = Path(os.getenv("CONFIG_LOCAL_PATH", _CONFIGLOCALPATH))

# _tzberlin: datetime.tzinfo = pytz.timezone("Europe/Berlin")

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    AliasPath,
    AliasChoices,
    field_validator,
    RootModel,
    AfterValidator,
    BeforeValidator,
)
from pydantic.fields import FieldInfo

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    EnvSettingsSource,
    YamlConfigSettingsSource,
    InitSettingsSource,
    DotEnvSettingsSource,
)

# secrets_dir='/var/run')
#
#     database_password: str
# settings = Settings(_secrets_dir='/var/run')
#
# TomlConfigSettingsSource using toml_file argument
# YamlConfigSettingsSource using yaml_file and yaml_file_encoding arguments
# JsonConfigSettingsSource using json_file and json_file_encoding arguments
#
# class MyCustomSource(EnvSettingsSource):
#     def prepare_field_value(
#         self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
#     ) -> Any:
#         if field_name == 'numbers':
#             return [int(x) for x in value.split(',')]
#         return json.loads(value)
#
#
# class MyCustomSettings(BaseSettings):
#     numbers: List[int]
#
#     @classmethod
#     def settings_customise_sources(
#         cls,
#         settings_cls: Type[BaseSettings],
#         init_settings: PydanticBaseSettingsSource,
#         env_settings: PydanticBaseSettingsSource,
#         dotenv_settings: PydanticBaseSettingsSource,
#         file_secret_settings: PydanticBaseSettingsSource,
#     ) -> Tuple[PydanticBaseSettingsSource, ...]:
#         return (MyCustomSource(settings_cls),)
#
#
# class Nested(BaseModel):
#     nested_field: str
#
#
# class TomlSettings(BaseSettings):
#     foobar: str
#     nested: Nested
#     model_config = SettingsConfigDict(toml_file='config.toml')
#
#     @classmethod
#     def settings_customise_sources(
#         cls,
#         settings_cls: Type[BaseSettings],
#         init_settings: PydanticBaseSettingsSource,
#         env_settings: PydanticBaseSettingsSource,
#         dotenv_settings: PydanticBaseSettingsSource,
#         file_secret_settings: PydanticBaseSettingsSource,
#     ) -> Tuple[PydanticBaseSettingsSource, ...]:
#         return (TomlConfigSettingsSource(settings_cls),)
#
# auth_key: str = Field(validation_alias='my_auth_key')
# api_key: str = Field(alias='my_api_key')
# redis_dsn: RedisDsn = Field(
#     'redis://user:pass@localhost:6379/1',
#     validation_alias=AliasChoices('service_redis_dsn', 'redis_url'),
# )
# pg_dsn: PostgresDsn = 'postgres://user:pa'ss@localhost:5432/foobar'
# amqp_dsn: AmqpDsn = 'amqp://user:pass@loc'alhost:5672/'
# special_function: ImportString[Callable[[Any], Any]] = 'math.cos'  (4)

# to override domains:
# export my_prefix_domains='["foo.com", "bar.com"]'
# domains: Set[str] = set()

# to override more_settings:
# export my_prefix_more_settings='{"foo": "x", "apple": 1}'
# more_settings: SubModel = SubModel()


class Redis(BaseModel):
    """Redis connection settings. Declared but currently not wired into `Settings`.

    Attributes:
        HOST: Hostname used outside a Kubernetes cluster.
        HOST_IN_CLUSTER: Hostname used when running inside the cluster, if different.
        PORT: TCP port.
    """

    HOST: str = Field(default="127.0.0.1")
    HOST_IN_CLUSTER: Optional[str] = Field(default=None)
    PORT: int = Field(default=6379)


class Gotify(BaseModel):
    """Credentials for one Gotify notification target.

    Attributes:
        APPNAME: Key used to look the entry up via `Settings.get_gotify_config_by_appname`.
        BASE_URL: Externally reachable base URL.
        BASE_URL_IN_CLUSTER: In-cluster base URL.
        TOKEN: Application token.
    """

    APPNAME: str
    BASE_URL: str
    BASE_URL_IN_CLUSTER: str
    TOKEN: str


class Cache(BaseModel):
    """How long a generated package index may be served without re-checking git.

    ``validate_assignment`` is on so that the CLI override in ``main.py``, which
    assigns to the live singleton, is validated just like a value coming from YAML
    or the environment.

    Attributes:
        freshness_minutes: Lifetime of a generated ``package.json`` in minutes.
            ``0`` re-checks git on every request.
    """

    model_config = ConfigDict(validate_assignment=True)

    freshness_minutes: float = Field(default=30.0, ge=0)


class UVICORN(BaseModel):
    """Arguments passed to `uvicorn.run` by ``main.py``.

    Attributes:
        port: TCP port to bind.
        app: Import string of the ASGI application. The shipped ``config.yaml``
            overrides the default with the correct ``"mipserver.app:app"``.
        host: Interface to bind.
        log_level: uvicorn's own log level, independent of ``LOGURU_LEVEL``.
        reload: Whether to watch the sources and restart on change. When enabled,
            the serving process is a child of the launcher.
    """

    port: int = Field(default=18891)
    app: str = Field(default="mipserver:app")
    host: str = Field(default="0.0.0.0")
    log_level: str = Field(default="info")
    reload: bool = Field(default=True)


class GotifyList(RootModel):
    """A YAML list of `Gotify` targets.

    Attributes:
        root: The configured targets.
    """

    root: List[Gotify]


class PackageNameGithubRepo(BaseModel):
    """Mapping of one requestable package name to its GitHub repository.

    Attributes:
        packagename: Name as the ``mip`` client requests it.
        githubrepo: ``owner/repo`` identifier.
    """

    packagename: str
    githubrepo: str


class PackageNameGithubRepoList(RootModel):
    """A YAML list of `PackageNameGithubRepo` entries.

    Attributes:
        root: The configured mappings. Anything not listed here is rejected.
    """

    root: List[PackageNameGithubRepo]


class Telegram(BaseModel):
    """Telegram bot credentials. Declared but currently not wired into `Settings`.

    Attributes:
        BOT_TOKEN: Bot token.
        BOT_CHATID: Target chat id.
        URL_PREFIX: Fixed API URL prefix.
    """

    BOT_TOKEN: str
    BOT_CHATID: str
    URL_PREFIX: Literal["https://api.telegram.org/bot"] = "https://api.telegram.org/bot"


class Mqtt(BaseModel):
    """MQTT broker connection settings.

    Note that the field names are UPPERCASE, so nested environment overrides such as
    ``MQTT__HOST`` do not reach them — see `AliasNormalizingYamlConfigSettingsSource`.

    Attributes:
        HOST: Broker hostname.
        PORT: Broker port.
        USERNAME: Login user.
        PASSWORD: Login password.
    """

    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=1883)
    USERNAME: str = Field()
    PASSWORD: str = Field()
    # guggle: Optional[str] = Field(default_factory=lambda: os.getenv("guggle"), validation_alias=AliasChoices("gummybear", "guggle"))

    # @field_validator('guggle', mode="before")
    # @classmethod
    # def validate_guggle(cls, v: Any, vinfo: ValidationInfo):
    #
    #     logger.debug(f"VALIDATE GUGGLE: {v} {vinfo=}")
    #     # vinfo=ValidationInfo(config={'title': 'Mqtt'}, context=None, data={'HOST': 'mosquittoi.heidk8.elasticc.io', 'PORT': 1883, 'USERNAME': 'venom', 'PASSWORD': 'kaiGh5esgael3OuH'}, field_name='guggle')
    #
    #     return v


# class MyEnvSettingsSource(EnvSettingsSource):
#     def __init__(self,
#                  settings_cls: type[BaseSettings],
#                  case_sensitive: bool | None = None,
#                  env_prefix: str | None = None,
#                  env_nested_delimiter: str | None = None,
#                  env_ignore_empty: bool | None = None,
#                  env_parse_none_str: str | None = None,
#                  env_parse_enums: bool | None = None):
#
#         super().__init__(
#             settings_cls=settings_cls,
#             case_sensitive=case_sensitive,
#             env_prefix=env_prefix,
#             env_nested_delimiter=env_nested_delimiter,
#             env_ignore_empty=env_ignore_empty,
#             env_parse_none_str=env_parse_none_str,
#             env_parse_enums=env_parse_enums)
#
#     # def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
#     #     v: Any = super().get_field_value(field, field_name)
#     #     # logger.debug(f"{field=} {field_name=}\n\t=> {v}")
#     #     return v
#
#     def prepare_field_value(self, field_name: str,
#                         field: FieldInfo,
#                         value: Any,
#                         value_is_complex: bool) -> Any:
#
#         v: Any = super().prepare_field_value(field_name, field, value, value_is_complex)
#         if isinstance(v, dict):
#             if field_name not in v and field_name in os.environ:
#                 v[field_name] = os.getenv(field_name)
#
#         logger.debug(f"{field_name=} {field=} {value=} {value_is_complex=}\n\t=> {type(v)=} {v}")
#
#         return v
#
#     @classmethod
#     def from_other(cls, other: EnvSettingsSource):
#         return MyEnvSettingsSource(
#             settings_cls=other.settings_cls,
#             case_sensitive=other.case_sensitive,
#             env_prefix=other.env_prefix,
#             env_nested_delimiter=other.env_nested_delimiter,
#             env_ignore_empty=other.env_ignore_empty,
#             env_parse_none_str=other.env_parse_none_str,
#             env_parse_enums=other.env_parse_enums
#         )


class AliasNormalizingYamlConfigSettingsSource(YamlConfigSettingsSource):
    """YamlConfigSettingsSource, but with top-level keys normalized to field names.

    The YAML files key their sections by the UPPERCASE aliases ("UVICORN", "CACHE", ...),
    whereas EnvSettingsSource emits field names ("uvicorn", "cache", ...). Both end up in
    the same merged dict under *different* keys, and pydantic prefers the alias key when
    validating -> YAML would always beat ENV, no matter in which order the sources are
    returned. Normalizing to field names restores the intended source precedence
    (init > env > yaml).

    This only covers the *top level*. `Mqtt` and `Gotify` declare UPPERCASE field
    names, so nested overrides such as ``MQTT__HOST`` still do not apply.
    """

    def __call__(self) -> Dict[str, object]:
        """Read the YAML files and rewrite their top-level keys to field names.

        Keys that match no field, by name or by alias and ignoring case, are passed
        through untouched so that unknown sections keep being handled by the
        ``extra="ignore"`` policy of `Settings`.

        Returns:
            The parsed YAML documents with normalized top-level keys.
        """
        by_lower_key: Dict[str, str] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            by_lower_key[field_name.lower()] = field_name
            if field.alias:
                by_lower_key[field.alias.lower()] = field_name

        return {by_lower_key.get(key.lower(), key): value for key, value in super().__call__().items()}


class Settings(BaseSettings):
    """Root of the configuration; instantiated once as :data:`settings`.

    Every field carries an UPPERCASE alias because that is how the YAML documents
    are keyed. All sections except ``CACHE`` are mandatory, so the module cannot be
    imported without a valid ``config.yaml``.

    Attributes:
        timezone: Timezone used when rendering timestamps; given as an IANA name.
        mqtt: MQTT broker settings.
        gotifylist: Gotify notification targets.
        uvicorn: Server settings consumed by ``main.py``.
        cache: Cache behaviour; optional, defaults apply when the section is absent.
        packagename_to_github_repo: The package-to-repository mapping. Acts as an
            allow-list: requests for unlisted packages are rejected.
    """

    # model_config = SettingsConfigDict(env_prefix='TAS_', case_sensitive=False, env_file='.env', env_file_encoding='utf-8')
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        populate_by_name=True,
        # env_prefix="TAS_",
        case_sensitive=False,
        yaml_file_encoding="utf-8",
        extra="ignore",  # ignore | forbid | allow
        protected_namespaces=(),
        env_nested_delimiter="__",
        # env_parse_enums=True,
        # alias_generator=AliasGenerator(
        #     validation_alias=to_camel,
        #     serialization_alias=to_pascal,
        # )
        yaml_file=[_CONFIGPATH, _CONFIGLOCALPATH],
    )

    timezone: datetime.tzinfo = Field(
        alias="TIMEZONE"
    )  # Annotated[datetime.tzinfo, BeforeValidator(lambda v: pytz.timezone(v))]

    # redis: Redis = Field(alias="REDIS")
    mqtt: Mqtt = Field(alias="MQTT")
    gotifylist: GotifyList = Field(alias="GOTIFY")
    uvicorn: UVICORN = Field(alias="UVICORN")
    cache: Cache = Field(alias="CACHE", default_factory=Cache)
    packagename_to_github_repo: PackageNameGithubRepoList = Field(alias="PACKAGENAME_TO_GITHUB_REPO")

    # HttpUrlString = Annotated[HttpUrl, AfterValidator(lambda v: str(v))]

    @field_validator("timezone", mode="before")
    @classmethod
    def validate_timezone(cls, v: object, vinfo: ValidationInfo) -> datetime.tzinfo:
        """Turn the configured IANA timezone name into a `datetime.tzinfo`.

        Args:
            v: The raw value, normally the timezone name as a string.
            vinfo: Validation context supplied by pydantic; used for logging only.

        Returns:
            The resolved timezone.

        Raises:
            pytz.exceptions.UnknownTimeZoneError: If the name is not a known timezone.
        """
        logger.debug(f"VALIDATE TIMEZONE: {type(v)=} {v} {vinfo=}")
        # VALIDATE TIMEZONE: type(v)=<class 'str'> Europe/Berlin vinfo=ValidationInfo(config={'title': 'Settings', 'extra_fields_behavior': 'ignore', 'validate_default': True, 'validate_by_alias': True, 'validate_by_name': True}, context=None, data={}, field_name='timezone')
        return pytz.timezone(str(v))

    def get_gotify_config_by_appname(self, appname: str) -> Optional[Gotify]:
        """Find a configured Gotify target by its application name.

        Args:
            appname: The ``APPNAME`` to look for; compared case-sensitively.

        Returns:
            The matching target, or ``None`` if no entry carries that name.
        """
        g: Gotify
        for g in self.gotifylist.root:
            if g.APPNAME == appname:
                return g

        return None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: InitSettingsSource,  # type: ignore
        env_settings: EnvSettingsSource,  # type: ignore
        dotenv_settings: DotEnvSettingsSource,  # type: ignore
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Select and order the settings sources.

        Dotenv and secrets files are deliberately dropped; the YAML source is
        swapped for `AliasNormalizingYamlConfigSettingsSource` so that environment
        variables can actually override YAML values.

        Args:
            settings_cls: The settings class being built.
            init_settings: Values passed to the constructor.
            env_settings: Values read from the environment.
            dotenv_settings: Values from a ``.env`` file; unused.
            file_secret_settings: Values from a secrets directory; unused.

        Returns:
            The active sources, highest precedence first.
        """
        # return init_settings, MyEnvSettingsSource.from_other(env_settings), YamlConfigSettingsSource(settings_cls)
        return init_settings, env_settings, AliasNormalizingYamlConfigSettingsSource(settings_cls)


settings: Settings = Settings()  # type: ignore

if __name__ == "__main__":
    pprint(settings.model_dump())
