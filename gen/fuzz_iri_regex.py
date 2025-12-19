#!/usr/bin/env python3
"""
Fuzz test to verify equivalence between:
  PCRE:  (?!_:).+:.+
  XSD:   [^_].*:.+|_[^:].*:.+
"""

import re
import random
import string

# PCRE pattern (with anchoring to match XSD behavior)
PCRE_PATTERN = re.compile(r"^(?!_:).+:.+$")

# XSD pattern (XSD regexes are implicitly anchored)
XSD_PATTERN = re.compile(r"^([^_].*:.+|_[^:].*:.+)$")


def generate_random_string(max_len=20):
    """Generate a random string with various characters."""
    length = random.randint(0, max_len)
    # Include characters that are interesting for our patterns
    chars = string.ascii_letters + string.digits + "_:.-/"
    return "".join(random.choice(chars) for _ in range(length))


def generate_edge_case_strings():
    """Generate strings specifically designed to test edge cases."""
    cases = [
        # Should NOT match (starts with _:)
        "_:",
        "_:foo",
        "_:foo:bar",
        "_:a",
        "_:::",
        # Should match (has : but doesn't start with _:)
        "a:b",
        "foo:bar",
        "_a:b",  # starts with _ but not _:
        "a_:b",
        "__:foo",  # starts with __ not _:
        "x:y:z",
        "http://example.com",
        "urn:uuid:12345",
        # Should NOT match (no colon or wrong structure)
        "",
        "a",
        "abc",
        "_",
        ":",
        "a:",
        ":b",
        "_a",
        # Edge cases with underscore and colon
        "_x:y",
        "x_:y",
        "_::",
        ":::",
        "a::",
    ]
    return cases


def test_string(s):
    """Test a string against both patterns and return results."""
    pcre_match = bool(PCRE_PATTERN.match(s))
    xsd_match = bool(XSD_PATTERN.match(s))
    return pcre_match, xsd_match


def main():
    print("Fuzzing PCRE vs XSD regex equivalence")
    print("=" * 50)
    print(f"PCRE: (?!_:).+:.+")
    print(f"XSD:  [^_].*:.+|_[^:].*:.+")
    print("=" * 50)

    failures = []
    total_tests = 0

    # Test edge cases first
    print("\nTesting edge cases...")
    edge_cases = generate_edge_case_strings()
    for s in edge_cases:
        total_tests += 1
        pcre_match, xsd_match = test_string(s)
        if pcre_match != xsd_match:
            failures.append((s, pcre_match, xsd_match))
        else:
            status = "✓ MATCH" if pcre_match else "✓ NO MATCH"
            print(f"  {repr(s):30} -> {status}")

    # Random fuzzing
    num_random = 100000
    print(f"\nRunning {num_random} random tests...")
    for i in range(num_random):
        s = generate_random_string()
        total_tests += 1
        pcre_match, xsd_match = test_string(s)
        if pcre_match != xsd_match:
            failures.append((s, pcre_match, xsd_match))

    # Also generate strings that are more likely to be interesting
    print("Running targeted random tests...")
    for _ in range(50000):
        # Strings starting with _
        s = "_" + generate_random_string(15)
        total_tests += 1
        pcre_match, xsd_match = test_string(s)
        if pcre_match != xsd_match:
            failures.append((s, pcre_match, xsd_match))

    for _ in range(50000):
        # Strings with colons
        parts = [generate_random_string(5) for _ in range(random.randint(2, 4))]
        s = ":".join(parts)
        total_tests += 1
        pcre_match, xsd_match = test_string(s)
        if pcre_match != xsd_match:
            failures.append((s, pcre_match, xsd_match))

    for _ in range(50000):
        # Strings starting with _:
        s = "_:" + generate_random_string(10)
        total_tests += 1
        pcre_match, xsd_match = test_string(s)
        if pcre_match != xsd_match:
            failures.append((s, pcre_match, xsd_match))

    # Report results
    print("\n" + "=" * 50)
    print(f"Total tests: {total_tests}")
    print(f"Failures: {len(failures)}")

    if failures:
        print("\nFAILURES:")
        for s, pcre, xsd in failures[:20]:  # Show first 20
            print(f"  {repr(s):30} PCRE={pcre}, XSD={xsd}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more")
        return 1
    else:
        print("\n✓ All tests passed! The patterns are equivalent.")
        return 0


if __name__ == "__main__":
    exit(main())
