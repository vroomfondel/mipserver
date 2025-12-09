import datetime

# https://docs.pydantic.dev/latest/concepts/pydantic_settings/

import os
import sys
from enum import StrEnum, auto
from functools import partial
from pathlib import Path
from pprint import pprint

import pytz
from typing import Any, Callable, Set, Type, Tuple, List, Dict, Optional, Literal, ClassVar, Annotated

from loguru import logger
from pydantic_core.core_schema import ValidationInfo

os.environ["LOGURU_LEVEL"] = os.getenv("LOGURU_LEVEL", "DEBUG")  # standard is DEBUG
logger.remove()  # remove default-handler
logger_fmt: str = "<g>{time}</> | <lvl>{level}</> | <c>{extra[classname]}:{function}:{line}</> - {message}"
# # https://buildmedia.readthedocs.org/media/pdf/loguru/latest/loguru.pdf
logger.add(
    sys.stderr, level=os.getenv("LOGURU_LEVEL", "DEBUG"), format=logger_fmt
)  # TRACE | DEBUG | INFO | WARN | ERROR |  FATAL
logger.configure(extra={"classname": "None"})


_CONFIGDIRPATH: Path = Path(__file__).parent.resolve()
_CONFIGDIRPATH = Path(os.getenv("CONFIG_DIR_PATH", _CONFIGDIRPATH))

_CONFIGPATH: Path = Path(_CONFIGDIRPATH, "config.yaml")
_CONFIGPATH = Path(os.getenv("CONFIG_PATH", _CONFIGPATH))

_CONFIGLOCALPATH: Path = Path(_CONFIGDIRPATH, "config.local.yaml")
_CONFIGLOCALPATH = Path(os.getenv("CONFIG_LOCAL_PATH", _CONFIGLOCALPATH))

# _tzberlin: datetime.tzinfo = pytz.timezone("Europe/Berlin")

from pydantic import (
    BaseModel,
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
    HOST: str = Field(default="127.0.0.1")
    HOST_IN_CLUSTER: Optional[str] = Field(default=None)
    PORT: int = Field(default=6379)


class Gotify(BaseModel):
    APPNAME: str
    BASE_URL: str
    BASE_URL_IN_CLUSTER: str
    TOKEN: str


class UVICORN(BaseModel):
    port: int = Field(default=18891)
    app: str = Field(default="mipserver:app")
    host: str = Field(default="0.0.0.0")
    log_level: str = Field(default="info")
    reload: bool = Field(default=True)


class GotifyList(RootModel):
    root: List[Gotify]


class PackageNameGithubRepo(BaseModel):
    packagename: str
    githubrepo: str


class PackageNameGithubRepoList(RootModel):
    root: List[PackageNameGithubRepo]


class Telegram(BaseModel):
    BOT_TOKEN: str
    BOT_CHATID: str
    URL_PREFIX: Literal["https://api.telegram.org/bot"] = "https://api.telegram.org/bot"


class Mqtt(BaseModel):
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


class Settings(BaseSettings):
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
    packagename_to_github_repo: PackageNameGithubRepoList = Field(alias="PACKAGENAME_TO_GITHUB_REPO")

    # HttpUrlString = Annotated[HttpUrl, AfterValidator(lambda v: str(v))]

    @field_validator("timezone", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any, vinfo: ValidationInfo) -> None | datetime.tzinfo:
        logger.debug(f"VALIDATE TIMEZONE: {type(v)=} {v} {vinfo=}")
        # VALIDATE TIMEZONE: type(v)=<class 'str'> Europe/Berlin vinfo=ValidationInfo(config={'title': 'Settings', 'extra_fields_behavior': 'ignore', 'validate_default': True, 'validate_by_alias': True, 'validate_by_name': True}, context=None, data={}, field_name='timezone')
        return pytz.timezone(str(v))

    def get_gotify_config_by_appname(self, appname: str) -> Optional[Gotify]:
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
        # return init_settings, MyEnvSettingsSource.from_other(env_settings), YamlConfigSettingsSource(settings_cls)
        return init_settings, env_settings, YamlConfigSettingsSource(settings_cls)


settings: Settings = Settings()  # type: ignore

if __name__ == "__main__":
    pprint(settings.model_dump())
