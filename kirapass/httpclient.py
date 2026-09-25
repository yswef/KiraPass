"""A small HTTP client built only on the python standard library.

Why not `requests`?  Because the old version died with
`ModuleNotFoundError: No module named requests` on any machine where the
package was not installed (phones, fresh Windows, locked lab PCs).  This
client needs nothing but python itself, and it gives exact control over the
three things this tool lives on:

* keep-alive connection reuse  -> real speed on a router
* connect timeout vs read timeout -> we can tell "unreachable" from "busy"
* reading the real reply body   -> we need the bytes, not a convenience layer
"""

from __future__ import annotations

import gzip
import http.client
import http.cookies
import socket
import ssl
import time
import urllib.parse
import zlib

from . import config
from .errors import NetError, classify

MAX_REDIRECTS = 8


class Response:
    """One HTTP reply, decoded but otherwise untouched."""

    __slots__ = ("status", "headers", "_body", "url", "elapsed_ms",
                 "history", "method", "request_headers", "reason")

    def __init__(self, status, headers, body, url, elapsed_ms, history,
                 method="GET", request_headers=None, reason=""):
        self.status = status
        self.headers = headers            # dict, keys lower-case
        self._body = body
        self.url = url
        self.elapsed_ms = elapsed_ms
        self.history = history            # list of urls passed through
        self.method = method
        self.request_headers = request_headers or {}
        self.reason = reason

    # -- body -------------------------------------------------------------
    @property
    def body(self) -> bytes:
        return self._body

    @property
    def text(self) -> str:
        return self.decode()

    def decode(self, limit: int = 0) -> str:
        raw = self._body
        if limit:
            raw = raw[:limit]
        charset = "utf-8"
        ctype = self.header("content-type")
        if "charset=" in ctype:
            charset = ctype.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return raw.decode(charset, "replace")
        except LookupError:
            return raw.decode("utf-8", "replace")

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    @property
    def location(self) -> str:
        return self.header("location")

    @property
    def length(self) -> int:
        return len(self._body)

    def is_redirect(self) -> bool:
        return self.status in (301, 302, 303, 307, 308) and bool(self.location)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "length": self.length,
            "url": self.url,
            "location": self.location,
            "ms": round(self.elapsed_ms),
        }


class CookieStore:
    """Minimal cookie jar (name/domain/path), enough for captive portals."""

    def __init__(self):
        self._jar = {}

    def update(self, url: str, set_cookie_headers) -> None:
        host = urllib.parse.urlsplit(url).hostname or ""
        for raw in set_cookie_headers:
            try:
                parsed = http.cookies.SimpleCookie()
                parsed.load(raw)
            except Exception:
                continue
            for name, morsel in parsed.items():
                domain = (morsel["domain"] or host).lstrip(".").lower()
                path = morsel["path"] or "/"
                self._jar[name] = {
                    "value": morsel.value,
                    "domain": domain,
                    "path": path,
                    "secure": bool(morsel["secure"]),
                }

    def header(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        path = parts.path or "/"
        out = []
        for name, c in self._jar.items():
            dom = c["domain"]
            if dom and not (host == dom or host.endswith("." + dom)):
                continue
            if not path.startswith(c["path"]):
                continue
            if c["secure"] and parts.scheme != "https":
                continue
            out.append(f"{name}={c['value']}")
        return "; ".join(out)

    def clear(self) -> None:
        self._jar.clear()

    def __len__(self) -> int:
        return len(self._jar)


class Session:
    """One connection + cookie store. Use one Session per worker thread."""

    def __init__(self, headers=None, connect_timeout=config.CONNECT_TIMEOUT,
                 read_timeout=config.READ_TIMEOUT, verify_tls=config.VERIFY_TLS,
                 allow_redirects=False):
        self.headers = dict(config.BASE_HEADERS)
        if headers:
            self.headers.update(headers)
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.verify_tls = verify_tls
        self.allow_redirects = allow_redirects
        self.cookies = CookieStore()
        self._conn = None
        self._key = None
        self.stats = {"requests": 0, "retries": 0, "bytes": 0}
        self._ssl_ctx = None

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False

    # -- connection -------------------------------------------------------
    def _ssl_context(self):
        if self._ssl_ctx is None:
            if self.verify_tls:
                self._ssl_ctx = ssl.create_default_context()
            else:
                self._ssl_ctx = ssl._create_unverified_context()
        return self._ssl_ctx

    def _connection(self, scheme, host, port):
        key = (scheme, host, port)
        if self._conn is not None and self._key == key:
            return self._conn
        self.close()
        if scheme == "https":
            conn = http.client.HTTPSConnection(
                host, port, timeout=self.connect_timeout,
                context=self._ssl_context())
        else:
            conn = http.client.HTTPConnection(
                host, port, timeout=self.connect_timeout)
        self._conn, self._key = conn, key
        return conn

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._key = None

    # -- requests ---------------------------------------------------------
    def request(self, method, url, params=None, data=None, headers=None,
                allow_redirects=None, timeout=None) -> Response:
        method = method.upper()
        if params:
            sep = "&" if urllib.parse.urlsplit(url).query else "?"
            url = url + sep + urllib.parse.urlencode(params, doseq=True)
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data, doseq=True).encode()
            post_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        elif isinstance(data, str):
            body = data.encode()
            post_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        elif isinstance(data, bytes):
            body = data
            post_headers = {"Content-Type": "application/octet-stream"}
        else:
            body = None
            post_headers = {}

        follow = self.allow_redirects if allow_redirects is None else allow_redirects
        history = []
        started = time.time()

        for _ in range(MAX_REDIRECTS + 1):
            resp = self._send_once(method, url, body, headers, post_headers,
                                   timeout)
            resp.history = list(history)
            if not (follow and resp.is_redirect()):
                resp.elapsed_ms = (time.time() - started) * 1000
                return resp
            history.append(url)
            target = urllib.parse.urljoin(url, resp.location)
            if resp.status == 303 or (resp.status in (301, 302) and method == "POST"):
                method, body, post_headers = "GET", None, {}
            url = target
        raise NetError("too_many_redirects", f"redirect loop at {url}", url)

    def get(self, url, **kw) -> Response:
        return self.request("GET", url, **kw)

    def post(self, url, **kw) -> Response:
        return self.request("POST", url, **kw)

    # -- the raw single round trip ---------------------------------------
    def _send_once(self, method, url, body, extra_headers, post_headers,
                   timeout) -> Response:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise NetError("proto", f"unsupported scheme: {parts.scheme!r}", url)
        host = parts.hostname or ""
        if not host:
            raise NetError("proto", f"no host in url: {url}", url)
        scheme = parts.scheme
        port = parts.port or (443 if scheme == "https" else 80)
        path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))

        headers = dict(self.headers)
        headers.update(post_headers)
        headers["Host"] = host if port in (80, 443) else f"{host}:{port}"
        headers["Accept-Encoding"] = "gzip, deflate"
        cookie = self.cookies.header(url)
        if cookie:
            headers["Cookie"] = cookie
        if extra_headers:
            headers.update(extra_headers)

        read_to = (timeout[1] if isinstance(timeout, (tuple, list))
                   else (timeout or self.read_timeout))
        connect_to = (timeout[0] if isinstance(timeout, (tuple, list))
                      else self.connect_timeout)

        last_exc = None
        for attempt in range(2):          # one silent retry for dead keep-alive
            try:
                conn = self._connection(scheme, host, port)
                if conn.sock is None:
                    conn.timeout = connect_to
                    # Opening the socket is its own phase: if it times out we
                    # must say "the router never answered the connection",
                    # not "the router never answered the request".  (Without
                    # this, python folds both into one TimeoutError and every
                    # dead router looked like a slow one.)
                    try:
                        conn.connect()
                    except (socket.timeout, TimeoutError) as exc:
                        self.close()
                        raise NetError("connect_timeout",
                                       f"{type(exc).__name__}: {exc}", url)
                conn.sock.settimeout(read_to)
                start = time.time()
                conn.request(method, path, body=body, headers=headers)
                raw = conn.getresponse()
                payload = raw.read()
                elapsed = (time.time() - start) * 1000
                payload = self._decompress(payload, raw.getheader("Content-Encoding"))
                hdrs = {k.lower(): v for k, v in raw.getheaders()}
                self.stats["requests"] += 1
                self.stats["bytes"] += len(payload)
                if raw.will_close:
                    self.close()
                self.cookies.update(url, raw.headers.get_all("Set-Cookie") or [])
                return Response(raw.status, hdrs, payload, url, elapsed, [],
                                method, headers, raw.reason)
            except NetError:
                raise
            except Exception as exc:
                err = classify(exc, url)
                last_exc = err
                self.close()
                if attempt == 0 and err.retryable:
                    self.stats["retries"] += 1
                    time.sleep(0.05)
                    continue
                raise err
        raise last_exc or NetError("unknown", "request failed", url)

    @staticmethod
    def _decompress(payload: bytes, encoding: str) -> bytes:
        enc = (encoding or "").lower()
        if "gzip" in enc:
            try:
                return gzip.decompress(payload)
            except Exception:
                return payload
        if "deflate" in enc:
            try:
                return zlib.decompress(payload)
            except Exception:
                try:
                    return zlib.decompress(payload, -zlib.MAX_WBITS)
                except Exception:
                    return payload
        return payload


def open_url(url: str, timeout=None, headers=None) -> Response:
    """One-shot GET with a throw-away session (used for quick checks)."""
    s = Session(headers=headers)
    try:
        return s.get(url, timeout=timeout)
    finally:
        s.close()


def local_ip() -> str:
    """Best-effort local IP, used to print the LAN link of the web UI."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
