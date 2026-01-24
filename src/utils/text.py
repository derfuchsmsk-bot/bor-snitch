import html

def escape(text: str) -> str:
    if text is None:
        return ""
    return html.escape(str(text))
