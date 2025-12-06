from typing import Union, List, Any, ClassVar

from pydantic import BaseModel, Field, ConfigDict, model_validator, model_serializer

from mipserver.datastructures.datatypes import SensorType

class ErrorResponse(BaseModel):
    error: str

class MIPServerFile(BaseModel):
    path: str  # e.g. "mein-paket/__init__.mpy"
    hash: str  # sha256 is there a type for that?!
    size: int

class MIPServerFileL(BaseModel):
    path: str
    hash: str

    @model_serializer
    def serialize_model(self) -> List[str]:
        return [self.path, self.hash]


class MIPServerPackageJson(BaseModel):
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

from mipserver import config
from loguru import logger

class MIPSRCPackageURLEntry(BaseModel):
    url_from: str
    url_to: str

    logger: ClassVar = logger.bind(classname=__qualname__)
    logger.level("INFO")

    @model_validator(mode="before")
    @classmethod
    def _populate_root(cls, v: Any) -> Any:

        cls.logger.debug(f"_populate_root_::{type(v)=} {v=}")

        if isinstance(v, list):
            assert len(v) == 2
            return {"url_from": v[0], "url_to": v[1]}

        return None



class MIPSRCPackageJson(BaseModel):
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
    sensor: SensorType


class Item(BaseModel):
    name: str
    price: float
    tax: float | None = None
    tags: list[str] = []
    description: Union[str, None] = Field(default=None, json_schema_extra={"example": "A very nice Item"})

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "name": "Foo",
                "description": "A very nice Item",
                "price": 35.4,
                "tax": 3.2,
            }
        })


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

