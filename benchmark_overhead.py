import timeit
import re

from backend.app.services.pdf_parser import FLOAT_PATTERNS, INT_PATTERNS

COMPILED_FLOAT_PATTERNS = [(n, re.compile(p, re.IGNORECASE), u) for n, p, u in FLOAT_PATTERNS]
COMPILED_INT_PATTERNS = [(n, re.compile(p, re.IGNORECASE), u) for n, p, u in INT_PATTERNS]

haystack = "Small text"

def test_original():
    for name, pattern, unit in FLOAT_PATTERNS:
        match = re.search(pattern, haystack, re.IGNORECASE)
    for name, pattern, unit in INT_PATTERNS:
        match = re.search(pattern, haystack, re.IGNORECASE)

def test_compiled():
    for name, pattern, unit in COMPILED_FLOAT_PATTERNS:
        match = pattern.search(haystack)
    for name, pattern, unit in COMPILED_INT_PATTERNS:
        match = pattern.search(haystack)

print("Original:", timeit.timeit(test_original, number=100000))
print("Compiled:", timeit.timeit(test_compiled, number=100000))
