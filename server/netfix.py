"""Network fixes applied once at import so outbound HTTPS works reliably.

This machine's DNS commonly returns IPv6-first addresses for Google hosts but
has no working IPv6 route, which makes TLS connects hang forever. The simplest
reliable fix is to reorder ``getaddrinfo`` results so IPv4 is tried first.
"""
import socket as _socket

_orig_getaddrinfo = _socket.getaddrinfo


def _prefer_ipv4(*args, **kwargs):
    """Return the original lookup with any IPv4 addresses moved to the front.

    When no IPv4 address exists (pure IPv6 host) the original order is kept so
    nothing that genuinely needs IPv6 breaks.
    """
    results = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in results if r[0] == _socket.AF_INET]
    if not ipv4:
        return results
    rest = [r for r in results if r[0] != _socket.AF_INET]
    return ipv4 + rest


try:
    _socket.getaddrinfo = _prefer_ipv4
except Exception:
    pass