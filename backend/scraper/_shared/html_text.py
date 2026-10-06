"""HTML job descriptions to plain text, for sources whose API hands back markup (freehire, Apify Glassdoor)."""
import re


def html_to_text(html_str: str) -> str:
    """Flatten HTML to plaintext, inserting newlines only at block boundaries (</p>, </li>, <br>, …) so inline markup (<b>, <a>) doesn't split words."""
    if not html_str:
        return ""
    try:
        from bs4 import BeautifulSoup
        s = re.sub(r"(?i)<br\s*/?>", "\n", html_str)
        s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|ul|ol)>", "\n", s)
        text = BeautifulSoup(s, "html.parser").get_text()  # no separator → inline words stay joined
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:
        import html as _html
        return _html.unescape(re.sub(r"<[^>]+>", " ", html_str)).strip()
