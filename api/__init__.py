try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version(__name__)
except Exception:
    import tomllib
    from pathlib import Path

    with open(Path(__file__).parent / "pyproject.toml", "rb") as _f:
        __version__ = tomllib.load(_f)["project"]["version"]
