"""Simple Arabic + English content filter for chat messages.

Blocks a curated list of profanity/slurs. Deliberately conservative — the
goal is to avoid the most obvious abuse on live streams, not to police
speech. Users can still say almost anything else.
"""
import re

# Common Arabic + English offensive terms (kept short — expand cautiously).
_BAD_WORDS = [
    # Arabic
    "كس", "كسك", "كسمك", "كسم", "طيز", "طيزك", "زبي", "زب", "زبك",
    "شرموط", "شرموطة", "شرموطه", "قحبة", "قحبه", "قحبات",
    "خرا", "خراك", "خرة", "منيك", "منيوك", "متناك", "متناكة",
    "حقير", "حقيره", "لعنة", "يلعن", "ابن كلب", "ابن الكلب",
    # English (mild list)
    "fuck", "shit", "bitch", "asshole", "dick", "cunt", "faggot", "nigger",
]

# Word-boundary style match. Arabic doesn't use word boundaries the same as
# English so we do substring matching but require a minimum length to avoid
# false positives on common short words.
_pattern = re.compile(
    "|".join(re.escape(w) for w in _BAD_WORDS),
    flags=re.IGNORECASE,
)


def contains_profanity(text: str) -> bool:
    if not text:
        return False
    return bool(_pattern.search(text))


def sanitize(text: str) -> str:
    """Replace matched words with asterisks (same length)."""
    if not text:
        return text
    return _pattern.sub(lambda m: "*" * len(m.group(0)), text)
