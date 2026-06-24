import time, urllib.parse, urllib.request

HIGHLIGHTS_URL = "https://www.rescuetime.com/anapi/highlights_post"

def post_highlight(api_key, description, source, today=None, opener=None, timeout=5, url=HIGHLIGHTS_URL):
    date_str = today or time.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "key": api_key,
        "highlight_date": date_str,
        "description": description[:255],
        "source": source,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    _open = opener or urllib.request.urlopen
    with _open(req, timeout=timeout) as resp:
        return getattr(resp, "status", None) or resp.getcode()
