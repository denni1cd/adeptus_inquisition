"""Baseline weakness: issue identity differs for equivalent whitespace."""
def normalize_issue(text):
    return text.strip().lower()
