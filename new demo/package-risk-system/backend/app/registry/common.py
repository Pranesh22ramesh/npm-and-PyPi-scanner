import re
from urllib.parse import urlsplit, quote
import httpx
from ..config import MAX_UPLOAD, MAX_RECENT

def package_name(name, ecosystem):
    pattern = r'(?:@[a-z0-9._-]+/)?[a-z0-9._-]+' if ecosystem == 'npm' else r'[A-Za-z0-9][A-Za-z0-9._-]*'
    if not re.fullmatch(pattern, name) or len(name) > 214:
        raise ValueError('Invalid package name.')
    return quote(name, safe='')

def download(url, hosts, limit=MAX_UPLOAD):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Registry returned a non-allowlisted HTTPS URL.')
    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
            with client.stream('GET', url, headers={'User-Agent':'package-risk-research/1.0'}) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError('Registry response exceeds download-size limit.')
                return bytes(data)
    except httpx.HTTPError as exc:
        raise ValueError('Registry request failed. Check package availability and network access.') from exc

def select_versions(releases, count):
    amount = MAX_RECENT if count == 'all' else int(count)
    if amount not in (2,3,5,MAX_RECENT):
        raise ValueError('Choose 2, 3, 5, or all recent versions.')
    if len(releases) < 2:
        raise ValueError('At least two compatible source releases are required.')
    return releases[-amount:]
