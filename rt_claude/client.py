import time, urllib.parse, urllib.request, urllib.error

HIGHLIGHTS_URL = "https://www.rescuetime.com/anapi/highlights_post"


class RescueTimeError(Exception):
    """A write to the RescueTime API was rejected."""


class PremiumRequiredError(RescueTimeError):
    """RescueTime rejected the write because the account needs a Premium plan.

    Daily Highlights are a premium-only feature; free/Lite accounts get a 400
    with a '# premium feature' body.
    """


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
    try:
        with _open(req, timeout=timeout) as resp:
            return getattr(resp, "status", None) or resp.getcode()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        if e.code == 400 and "premium" in detail.lower():
            raise PremiumRequiredError(
                "RescueTime Daily Highlights require a Premium plan."
            )
        raise
