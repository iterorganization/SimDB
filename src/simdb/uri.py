from urllib.parse import urlparse, ParseResult
from pathlib import Path
from typing import Dict, Union, Optional


class Query:
    _args: Dict[str, Union[None, str]] = {}

    def __init__(self, query: str):
        for arg in query.split('&'):
            key, *value = arg.split('=')
            if value:
                self._args[key] = '='.join(value)
            else:
                self._args[key] = None

    def __str__(self):
        "&".join(f"{k}={v}" for k, v in self._args.items())

    def __bool__(self):
        return len(self._args) > 0


class URI:
    scheme: Optional[str]
    query: Optional[Query]
    path: Optional[Path]
    authority: Optional[str]
    fragment: Optional[str]

    def __init__(self, uri: Union[str, "URI", None]=None, *, scheme=None, path=None):
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
            self.path = path
        if not self.scheme:
            raise ValueError("No scheme specified")

    @property
    def uri(self):
        uri = f"{self.scheme}:"
        if self.authority:
            path = ""
            if self.path is not None:
                path = self.path if self.path.is_absolute() else "/" / self.path
            uri += f"{self.authority}{path}"
        elif self.path:
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
