from urllib.parse import urlparse, ParseResult
from pathlib import Path
from typing import Dict, Union, Optional


class Query:
    """
    Class representing the URI query parameters.
    """

    _args: Dict[str, Optional[str]] = {}

    def __init__(self, query: str):
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

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self._args.get(name) or default

    def remove(self, name: str) -> None:
        del self._args[name]


class URI:
    """
    Class for parsing and representing a URI.
    """

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
        self.authority: Optional[str] = None
        self.fragment: Optional[str] = None

        if uri is not None:
            result: ParseResult = urlparse(str(uri))
            self.scheme = result.scheme
            self.query = Query(result.query)
            self.path = Path(result.path)
            self.authority = result.netloc
            self.fragment = result.fragment
        if scheme is not None:
            self.scheme = scheme
        if path is not None:
            self.path = Path(path)
        if not self.scheme:
            raise ValueError("No scheme specified")

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
            uri += f"{self.authority}{path}"
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
