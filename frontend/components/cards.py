# Optional helper if you later want to generate richer HTML for cards.
# Currently kept simple in app.py's `card()` function to reduce imports.
def truncate(text: str, n: int = 80) -> str:
    return (text[: n - 1] + "…") if text and len(text) > n else (text or "")
