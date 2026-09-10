import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata",
}


def _canonical_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address):
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        return mapped
    return addr


def _ip_is_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    addr = _canonical_ip(addr)
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return True
    for net in BLOCKED_NETWORKS:
        try:
            if addr in net:
                return True
        except TypeError:
            continue
    return False


def is_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if hostname is None:
        return False
    if hostname.lower().rstrip(".") in BLOCKED_HOSTNAMES:
        return False

    try:
        literal = ipaddress.ip_address(hostname)
        return not _ip_is_blocked(literal)
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    if not infos:
        return False

    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if _ip_is_blocked(addr):
            return False
    return True
