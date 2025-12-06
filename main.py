import uvicorn

from mipserver.config import settings
# also sets loguru.logger defaults...

from loguru import logger

def main() -> None:
    logger.info(f"{__file__}::MAIN")
    uvicorn.run(
        app=settings.uvicorn.app,
        host=settings.uvicorn.host,
        port=settings.uvicorn.port,
        log_level=settings.uvicorn.log_level,
        reload=settings.uvicorn.reload
    )

if __name__ == "__main__":
    main()


# https://plainenglish.io/blog/unit-testing-in-python-structure-57acd51da923#directory-layout
# mpu <-- Root of the git repository
# ├── mpu <-- Root of the package
# │   ├── datastructures/
# │   │   ├── __init__.py
# │   │   └── trie
# │   │       ├── char_trie.py
# │   │       └── __init__.py
# │   ├── geometry.py
# │   ├── image.py
# │   ├── __init__.py
# │   ├── io.py
# │   └── _version.py
# ├── README.md
# ├── requirements-dev.in
# ├── requirements-dev.txt
# ├── tests/
# │   ├── files/
# │   ├── test_char_trie.py
# │   ├── test_datastructures.py
# │   ├── test_geometry.py
# │   ├── test_image.py
# │   ├── test_io.py
# │   └── test_main.py
# └── tox.ini