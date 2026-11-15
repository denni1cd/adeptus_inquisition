"""Candidate improvement: stable semantic whitespace normalization."""
def normalize_issue(text):
    return " ".join(text.lower().split())
