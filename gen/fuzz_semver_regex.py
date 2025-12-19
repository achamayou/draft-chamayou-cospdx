#!/usr/bin/env python3
"""
Fuzz testing script to verify PCRE and XSD semver regex equivalence.

This script tests that the PCRE and XSD versions of the semver regex
match exactly the same set of strings.
"""

import re
import random
import string
import sys
from typing import Tuple, List

# PCRE version (original)
PCRE_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"

# XSD version (converted) - Python re module can handle this too
# Main differences: \d -> [0-9], (?:...) -> (...)
XSD_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$"

# Compile both patterns
pcre_regex = re.compile(PCRE_PATTERN)
xsd_regex = re.compile(XSD_PATTERN)


def matches_pcre(s: str) -> bool:
    """Check if string matches PCRE pattern."""
    return pcre_regex.match(s) is not None


def matches_xsd(s: str) -> bool:
    """Check if string matches XSD pattern."""
    return xsd_regex.match(s) is not None


def compare(s: str) -> Tuple[bool, bool, bool]:
    """
    Compare both regex matches.
    Returns (pcre_match, xsd_match, equivalent)
    """
    pcre = matches_pcre(s)
    xsd = matches_xsd(s)
    return pcre, xsd, pcre == xsd


# =============================================================================
# Test Case Generators
# =============================================================================

def valid_semver_examples() -> List[str]:
    """Generate known valid semver strings."""
    return [
        # Basic versions
        "0.0.0",
        "0.0.1",
        "0.1.0",
        "1.0.0",
        "1.2.3",
        "10.20.30",
        "999.999.999",
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-0.3.7",
        "1.0.0-x.7.z.92",
        "1.0.0-x-y-z.-",
        
        # With build metadata
        "1.0.0+build",
        "1.0.0+build.123",
        "1.0.0+20130313144700",
        "1.0.0-beta+exp.sha.5114f85",
        "1.0.0+21AF26D3--117B344092BD",
        
        # Pre-release with numbers
        "1.0.0-0",
        "1.0.0-1",
        "1.0.0-11",
        "1.0.0-alpha.0",
        "1.0.0-alpha.1",
        "1.0.0-1.2.3",
        
        # Pre-release with alphanumeric
        "1.0.0-alpha",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0-rc.1+build.1",
        
        # Edge cases that should be valid
        "0.0.4",
        "1.2.3-0123alpha",  # Valid: starts with digit, contains alpha
        "1.2.3-alpha0123",  # Valid: starts with alpha
        "1.2.3-a-b-c",
        "1.2.3-a.b.c",
        "1.2.3-1a",
        "1.2.3-a1",
        "1.2.3--",
        "1.2.3---",
        "1.2.3----",
        "1.2.3-a-",
        "1.2.3--a",
        "1.2.3-a--b",
        
        # Large numbers
        "99999999999999999999.99999999999999999999.99999999999999999999",
        
        # Complex pre-release
        "1.0.0-alpha.1.beta.2.gamma.3",
        "1.0.0-x.y.z.a.b.c.d.e.f.g",
        
        # Complex build metadata  
        "1.0.0+a.b.c.d.e.f",
        "1.0.0-alpha+a.b.c",
        
        # Mixed case
        "1.0.0-ALPHA",
        "1.0.0-Alpha",
        "1.0.0-aLpHa",
        "1.0.0+BUILD",
        "1.0.0+Build",
        "1.0.0+bUiLd",
    ]


def invalid_semver_examples() -> List[str]:
    """Generate known invalid semver strings."""
    return [
        # Empty string
        "",
        
        # Missing components
        "1",
        "1.2",
        "1.2.",
        ".1.2",
        "1..2",
        "1.2.3.",
        ".1.2.3",
        "1.2.3.4",
        
        # Leading zeros (invalid for numeric identifiers)
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2.3-01",  # Leading zero in numeric pre-release
        "1.2.3-1.01",  # Leading zero in numeric pre-release
        
        # But these alphanumeric ones with leading zeros ARE valid
        # "1.2.3-0alpha" is valid because it contains letters
        
        # Invalid characters
        "1.2.3-alpha_beta",
        "1.2.3-alpha beta",
        "1.2.3-alpha\tbeta",
        "1.2.3-alpha\nbeta",
        "1.2.3+build_info",
        "1.2.3+build info",
        "v1.2.3",
        "1.2.3v",
        "=1.2.3",
        "1.2.3=",
        
        # Wrong separators
        "1-2-3",
        "1_2_3",
        "1,2,3",
        "1;2;3",
        
        # Negative numbers
        "-1.2.3",
        "1.-2.3",
        "1.2.-3",
        
        # Decimal numbers
        "1.2.3.4",
        "1.2.3.0",
        
        # Empty pre-release/build
        "1.2.3-",
        "1.2.3+",
        "1.2.3-+",
        "1.2.3-.",
        "1.2.3+.",
        "1.2.3-.alpha",
        "1.2.3+.build",
        "1.2.3-alpha.",
        "1.2.3+build.",
        "1.2.3-alpha..beta",
        "1.2.3+build..info",
        
        # Invalid pre-release
        "1.2.3-alpha+",
        "1.2.3-alpha+build+extra",
        
        # Whitespace
        " 1.2.3",
        "1.2.3 ",
        " 1.2.3 ",
        "1. 2.3",
        "1 .2.3",
        
        # Special characters in wrong places
        "1.2.3-alpha@beta",
        "1.2.3-alpha#beta",
        "1.2.3-alpha$beta",
        "1.2.3-alpha%beta",
        "1.2.3-alpha^beta",
        "1.2.3-alpha&beta",
        "1.2.3-alpha*beta",
        "1.2.3-alpha(beta",
        "1.2.3-alpha)beta",
        "1.2.3-alpha[beta",
        "1.2.3-alpha]beta",
        "1.2.3-alpha{beta",
        "1.2.3-alpha}beta",
        "1.2.3-alpha|beta",
        "1.2.3-alpha\\beta",
        "1.2.3-alpha/beta",
        "1.2.3-alpha:beta",
        "1.2.3-alpha;beta",
        "1.2.3-alpha'beta",
        '1.2.3-alpha"beta',
        "1.2.3-alpha<beta",
        "1.2.3-alpha>beta",
        "1.2.3-alpha,beta",
        "1.2.3-alpha?beta",
        "1.2.3-alpha`beta",
        "1.2.3-alpha~beta",
        "1.2.3-alpha!beta",
        
        # Unicode
        "1.2.3-αlpha",
        "1.2.3-Ωmega",
        "1.2.3-日本語",
        "1.2.3+بناء",
        
        # Hex-like but not valid
        "0x1.0x2.0x3",
        "1.2.3-0x1",
        
        # Other edge cases
        "1.2.3--.",
        "1.2.3-.-",
        "1.2.3+--.",
        "1.2.3+.-",
    ]


def generate_random_version() -> str:
    """Generate a random version-like string."""
    major = random.choice([0, random.randint(0, 100)])
    minor = random.choice([0, random.randint(0, 100)])
    patch = random.choice([0, random.randint(0, 100)])
    
    version = f"{major}.{minor}.{patch}"
    
    # Maybe add pre-release
    if random.random() < 0.5:
        pre = generate_random_prerelease()
        version += f"-{pre}"
    
    # Maybe add build metadata
    if random.random() < 0.3:
        build = generate_random_build()
        version += f"+{build}"
    
    return version


def generate_random_prerelease() -> str:
    """Generate a random pre-release identifier."""
    parts = []
    num_parts = random.randint(1, 5)
    
    for _ in range(num_parts):
        part_type = random.choice(["numeric", "alpha", "mixed", "hyphen"])
        if part_type == "numeric":
            # Avoid leading zeros for multi-digit
            if random.random() < 0.3:
                parts.append("0")
            else:
                parts.append(str(random.randint(1, 999)))
        elif part_type == "alpha":
            length = random.randint(1, 10)
            parts.append(''.join(random.choices(string.ascii_letters, k=length)))
        elif part_type == "mixed":
            length = random.randint(1, 10)
            parts.append(''.join(random.choices(string.ascii_letters + string.digits + "-", k=length)))
        elif part_type == "hyphen":
            parts.append("-" * random.randint(1, 3))
    
    return '.'.join(parts)


def generate_random_build() -> str:
    """Generate a random build metadata string."""
    parts = []
    num_parts = random.randint(1, 4)
    
    for _ in range(num_parts):
        length = random.randint(1, 10)
        parts.append(''.join(random.choices(string.ascii_letters + string.digits + "-", k=length)))
    
    return '.'.join(parts)


def generate_malformed_version() -> str:
    """Generate intentionally malformed version strings."""
    templates = [
        lambda: f"{random.randint(0, 99)}.{random.randint(0, 99)}",  # Missing patch
        lambda: f"{random.randint(0, 99)}",  # Only major
        lambda: f"0{random.randint(1, 9)}.0.0",  # Leading zero
        lambda: f"0.0{random.randint(1, 9)}.0",  # Leading zero
        lambda: f"0.0.0{random.randint(1, 9)}",  # Leading zero
        lambda: f"1.2.3-0{random.randint(1, 9)}",  # Leading zero in numeric prerelease
        lambda: "1.2.3-",  # Empty prerelease
        lambda: "1.2.3+",  # Empty build
        lambda: "1.2.3-alpha.",  # Trailing dot in prerelease
        lambda: "1.2.3+build.",  # Trailing dot in build
        lambda: "1.2.3-.alpha",  # Leading dot in prerelease
        lambda: "1.2.3-alpha..beta",  # Double dot
        lambda: "v1.2.3",  # Leading v
        lambda: " 1.2.3",  # Leading space
        lambda: "1.2.3 ",  # Trailing space
        lambda: f"1.2.3-alpha_{random.randint(0,9)}",  # Invalid char
        lambda: f"1.2.3-{random.choice(['@', '#', '$', '%', '^', '&', '*'])}",
        lambda: "-1.2.3",  # Negative major
        lambda: "1.2.3.4",  # Extra component
        lambda: ".1.2.3",  # Leading dot
        lambda: "1.2.3.",  # Trailing dot
        lambda: "1..2.3",  # Double dot
        lambda: "",  # Empty string
    ]
    
    return random.choice(templates)()


def generate_completely_random() -> str:
    """Generate completely random string."""
    length = random.randint(0, 50)
    chars = string.printable
    return ''.join(random.choices(chars, k=length))


def generate_boundary_cases() -> List[str]:
    """Generate boundary test cases."""
    cases = []
    
    # Test numbers at boundaries
    for n in [0, 1, 9, 10, 99, 100, 999, 1000]:
        cases.append(f"{n}.0.0")
        cases.append(f"0.{n}.0")
        cases.append(f"0.0.{n}")
        
    # Leading zeros edge cases
    for n in range(0, 20):
        cases.append(f"0{n}.0.0")
        cases.append(f"0.0{n}.0")
        cases.append(f"0.0.0{n}")
        cases.append(f"1.2.3-0{n}")
        # These should be valid (alphanumeric)
        cases.append(f"1.2.3-0{n}a")
        cases.append(f"1.2.3-a0{n}")
        
    # Pre-release numeric edge cases
    for n in [0, 1, 10, 100]:
        cases.append(f"1.2.3-{n}")
        
    # Empty parts
    cases.extend([
        "1.2.3-",
        "1.2.3+",
        "1.2.3-+",
        "1.2.3-a.",
        "1.2.3-.a",
        "1.2.3-a..",
        "1.2.3-..a",
        "1.2.3+a.",
        "1.2.3+.a",
    ])
    
    # Hyphen-only identifiers
    cases.extend([
        "1.2.3--",
        "1.2.3---",
        "1.2.3-a-",
        "1.2.3--a",
        "1.2.3-a--b",
        "1.2.3-a-b-c",
        "1.2.3+--",
        "1.2.3+a--b",
    ])
    
    # Single characters
    for c in string.ascii_letters + string.digits + "-":
        cases.append(f"1.2.3-{c}")
        cases.append(f"1.2.3+{c}")
        
    # Invalid single characters
    for c in "@#$%^&*()_+=[]{}|\\:;<>?,/`~!":
        cases.append(f"1.2.3-{c}")
        cases.append(f"1.2.3+{c}")
        
    return cases


# =============================================================================
# Test Runner
# =============================================================================

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: List[Tuple[str, bool, bool]] = []
    
    def add_result(self, test_input: str, pcre: bool, xsd: bool):
        if pcre == xsd:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append((test_input, pcre, xsd))
    
    def print_summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"RESULTS: {self.passed}/{total} passed, {self.failed} failed")
        print(f"{'='*60}")
        
        if self.failures:
            print("\nFAILURES (PCRE != XSD):")
            print("-" * 60)
            for test_input, pcre, xsd in self.failures[:50]:  # Limit output
                print(f"  Input: {repr(test_input)}")
                print(f"    PCRE: {pcre}, XSD: {xsd}")
            if len(self.failures) > 50:
                print(f"  ... and {len(self.failures) - 50} more failures")


def run_tests(test_cases: List[str], description: str, results: TestResults, verbose: bool = False):
    """Run tests on a list of test cases."""
    print(f"\nTesting: {description} ({len(test_cases)} cases)")
    
    for test_input in test_cases:
        pcre, xsd, equiv = compare(test_input)
        results.add_result(test_input, pcre, xsd)
        
        if verbose or not equiv:
            status = "✓" if equiv else "✗"
            print(f"  {status} {repr(test_input)}: PCRE={pcre}, XSD={xsd}")


def main():
    print("=" * 60)
    print("Semver Regex Equivalence Fuzz Test")
    print("=" * 60)
    print(f"\nPCRE Pattern:\n  {PCRE_PATTERN}")
    print(f"\nXSD Pattern:\n  {XSD_PATTERN}")
    
    results = TestResults()
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    # 1. Test valid semver examples
    run_tests(valid_semver_examples(), "Valid semver examples", results, verbose)
    
    # 2. Test invalid semver examples
    run_tests(invalid_semver_examples(), "Invalid semver examples", results, verbose)
    
    # 3. Test boundary cases
    run_tests(generate_boundary_cases(), "Boundary cases", results, verbose)
    
    # 4. Fuzz with random valid-ish versions
    num_random_versions = 100_000
    print(f"\nTesting: Random version-like strings ({num_random_versions} cases)")
    for _ in range(num_random_versions):
        test_input = generate_random_version()
        pcre, xsd, equiv = compare(test_input)
        results.add_result(test_input, pcre, xsd)
        if not equiv:
            print(f"  ✗ {repr(test_input)}: PCRE={pcre}, XSD={xsd}")
    
    # 5. Fuzz with malformed versions
    num_malformed = 50_000
    print(f"\nTesting: Malformed version strings ({num_malformed} cases)")
    for _ in range(num_malformed):
        test_input = generate_malformed_version()
        pcre, xsd, equiv = compare(test_input)
        results.add_result(test_input, pcre, xsd)
        if not equiv:
            print(f"  ✗ {repr(test_input)}: PCRE={pcre}, XSD={xsd}")
    
    # 6. Fuzz with completely random strings
    num_random = 100_000
    print(f"\nTesting: Completely random strings ({num_random} cases)")
    for _ in range(num_random):
        test_input = generate_completely_random()
        pcre, xsd, equiv = compare(test_input)
        results.add_result(test_input, pcre, xsd)
        if not equiv:
            print(f"  ✗ {repr(test_input)}: PCRE={pcre}, XSD={xsd}")
    
    # 7. Test all single-character variations
    print("\nTesting: Single character edge cases")
    single_char_cases = []
    for c in string.printable:
        single_char_cases.append(c)
        single_char_cases.append(f"1.2.3{c}")
        single_char_cases.append(f"1.2.3-{c}")
        single_char_cases.append(f"1.2.3+{c}")
        single_char_cases.append(f"1.2.3-a{c}b")
        single_char_cases.append(f"1.2.3+a{c}b")
    
    for test_input in single_char_cases:
        pcre, xsd, equiv = compare(test_input)
        results.add_result(test_input, pcre, xsd)
        if not equiv:
            print(f"  ✗ {repr(test_input)}: PCRE={pcre}, XSD={xsd}")
    
    # 8. Test various combinations of dots and hyphens
    print("\nTesting: Dot and hyphen combinations")
    combos = []
    for dots in range(0, 6):
        for hyphens in range(0, 4):
            base = "1.2.3-" + "." * dots + "-" * hyphens
            combos.append(base)
            combos.append(base + "a")
            combos.append("a" + base)
    
    for test_input in combos:
        pcre, xsd, equiv = compare(test_input)
        results.add_result(test_input, pcre, xsd)
        if not equiv:
            print(f"  ✗ {repr(test_input)}: PCRE={pcre}, XSD={xsd}")
    
    # Print final summary
    results.print_summary()
    
    # Return exit code based on results
    return 0 if results.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
