from urllib3.util.url import parse_url, Url, LocationParseError
from pathlib import Path
from typing import Dict, Union, Optional


class URIParserError(ValueError):
    def __init__(self, msg: str):
        super().__init__(msg)


class Query:
    """
    Class representing the URI query parameters.
    """

    _args: Dict[str, Optional[str]]

    def __init__(self, query: Optional[str]):
        query = "" if query is None else query
        self._args = {}
        for arg in query.split("&"):
            key, *value = arg.split("=")
            if key and value:
                self._args[key] = "=".join(value)
            elif key:
                self._args[key] = None

    def __str__(self):
        return "&".join(f"{k}={v}" for k, v in self._args.items())

    def __bool__(self):
        return len(self._args) > 0

    def __contains__(self, item) -> bool:
        return item in self._args

    def __getitem__(self, name):
        return self._args[name]

    def get(self, name: str, *, default: Optional[str] = None) -> Optional[str]:
        return self._args.get(name, default)

    def set(self, name: str, value: str) -> None:
        self._args[name] = value

    def remove(self, name: str) -> None:
        del self._args[name]


class Authority:
    """
    Class representing URI authority.
    """

    __slots__ = ("host", "port", "auth")

    def __init__(self, host: Optional[int], port: Optional[int], auth: Optional[str]):
        self.host: Optional[str] = host
        self.port: Optional[int] = port
        self.auth: Optional[str] = auth

    @classmethod
    def empty(cls):
        return cls(None, None, None)

    def __bool__(self):
        return bool(self.host) or bool(self.port) or bool(self.auth)

    def __str__(self):
        string = ""
        if self.host:
            string = f"{self.host}"
        if self.auth:
            string = f"{self.auth}@{string}"
        if self.port is not None:
            string = f"{string}:{self.port}"
        return string

    def __repr__(self):
        return f"Authority({self.host}, {self.port}, {self.auth})"


class URI:
    """
    Class for parsing and representing a URI.
    """

    __slots__ = ("scheme", "query", "path", "authority", "fragment")

    def __init__(self, uri: Union[str, "URI", None] = None, *, scheme=None, path=None):
        """
        Create a URI object by either parsing a URI string or copying from an existing URI object.

        :param uri: A URI string, another URI to copy from or None for an empty URI.
        :param scheme: The URI scheme. Takes precedence over any scheme found from the URI argument.
        :param path: The URI path. Takes precedence over any path found from the URI argument.
        """
        self.scheme: Optional[str] = None
        self.query: Optional[Query] = None
        self.path: Optional[Path] = None
        self.authority: Authority = Authority.empty()
        self.fragment: Optional[str] = None

        if uri is not None:
            try:
                result: Url = parse_url(str(uri))
            except LocationParseError:
                raise URIParserError("failed to parse URI")
            self.scheme = result.scheme
            self.query = Query(result.query)
            self.authority = Authority(result.host, result.port, result.auth)
            if result.path is not None:
                if (
                    self.scheme == "imas"
                    and not self.authority
                    and result.path.startswith("/")
                ):
                    self.path = Path(result.path[1:])
                else:
                    self.path = Path(result.path)
            self.fragment = result.fragment
        if scheme is not None:
            self.scheme = scheme
        if path is not None:
            self.path = Path(path)
        if not self.scheme:
            raise URIParserError("failed to parse URI: no scheme specified")

    @property
    def uri(self) -> str:
        """
        Return the URI object as a URI string.

        :return: A string representation of the URI.
        """
        uri = f"{self.scheme}:"
        if self.authority:
            path = ""
            if self.path and str(self.path) != ".":
                path = self.path if self.path.is_absolute() else "/" / self.path
            uri += f"//{self.authority}{path}"
        elif self.path and str(self.path) != ".":
            uri += f"{self.path}"
        if self.query:
            uri += f"?{self.query}"
        if self.fragment:
            uri += f"#{self.fragment}"
        return uri

    def __repr__(self):
        return f"URI({self.uri})"

    def __str__(self):
        return self.uri

    def __eq__(self, other):
        return self.uri == other.uri
