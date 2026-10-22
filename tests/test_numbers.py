"""Tests for `check_numbers` and the context it reads.

The tool used to read no context, so it flagged correct Estonian:

1. THOUSANDS. Any single comma group was an English thousands separator,
   but in Estonian the comma is the decimal separator: `1,250 kg` and
   `3,142` are decimals, and the suggestion `1 250` multiplied the value
   by 1000. Only two or more groups (1,500,000) or a group before a period
   decimal (1,500.50) are unambiguous, and 1,500,000.50 is one issue, not a
   thousands issue plus a decimal issue on `000.50`.

2. DECIMALS. Every d.d was an English decimal, including the times, dates,
   section and version numbers Estonian writes with a period: kell 10.30,
   10.30-12.00, 14.05, punkt 3.2, § 3.2, Python 3.12, v1.2.

3. A decimal at a sentence end (`Pi on 3.14.`) was missed, because the
   period after it read as one more group.

Every false positive is pinned clean, every true positive the tool caught
before is pinned as still caught, and each skip rule gets a case that only
that rule explains (10.20 is no quarter hour and no date, so `kell 10.20`
tests the kell rule alone).

Run via:

    uv run python tests/test_numbers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server

EN_DASH = chr(0x2013)

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"  FAIL {label} {detail}")


def found(text: str) -> list[tuple[str, str, str]]:
    return [(i["rule"], i["text"], i["suggestion"])
            for i in server.check_numbers(text)["issues"]]


def expect_clean(cases: list[str]) -> None:
    for text in cases:
        got = found(text)
        check(f"clean: {text!r}", got == [], str(got))


def expect_flags(cases: dict[str, list[tuple[str, str, str]]]) -> None:
    for text, want in cases.items():
        got = found(text)
        check(f"flags: {text!r}", got == want, f"want {want}, got {got}")


def single_comma_group_is_a_decimal() -> None:
    print("thousands-separator: one comma group is an Estonian decimal")
    expect_clean([
        "1,250 kg",
        "Pi on umbes 3,142",
        "Kaal oli 1,500.",
        "Päeval 14.05.2026 maksis pi umbes 3,14.",
    ])


def unambiguous_thousands_still_flag() -> None:
    print("thousands-separator: two groups or a period decimal after one")
    expect_flags({
        "Linnas elab 1,500,000 inimest.":
            [("thousands-separator", "1,500,000", "1 500 000")],
        "Linnas elab 1,500,000.":
            [("thousands-separator", "1,500,000", "1 500 000")],
        "Hind oli 1,500.50 eurot.":
            [("thousands-separator", "1,500.50", "1 500,50")],
        # One issue for the whole number; `000.50` is not a decimal of its own.
        "Kokku 1,500,000.50 eurot.":
            [("thousands-separator", "1,500,000.50", "1 500 000,50")],
    })
    r = server.check_numbers("Kokku 1,500,000.50 eurot.")
    check("1,500,000.50 is reported at its start",
          [i["position"] for i in r["issues"]] == [6], str(r["issues"]))


def times_are_skipped() -> None:
    print("decimal-separator: times")
    expect_clean([
        "kell 10.30",
        "kell 9.15-17.00",
        "10.30-12.00",
        f"kell 9.15{EN_DASH}17.00",
        f"10.30{EN_DASH}12.00",
        # Each rule on its own: 10.20 and 12.40 are no quarter hour and no date.
        "kell 10.20",
        "Kell oli juba 10.20.",
        "kella 10.20-ni",
        "kl 9.20",
        "kl. 9.20",
        "10.20-12.40",
        f"10.20 {EN_DASH} 12.40",
        "kell 9.20-17.40",
        "Kohtume 10.30.",
        "Uks avatakse 9.15.",
        "Pood suletakse 17.00.",
    ])


def dates_are_skipped() -> None:
    print("decimal-separator: dates")
    expect_clean([
        "Kohtume 14.05",
        "Kohtume 14.05.",
        "Kohtume 14.05.2026",
        "Kohtume 14.05.2026.",
        "Kohtume 1.05",
        "Kohtume 1.5.",
        "Tähtaeg on 31.12 ja 1.01.",
    ])


def section_numbers_are_skipped() -> None:
    print("decimal-separator: section and clause numbers")
    expect_clean([
        "punkt 3.2", "§ 3.2", "lõige 2.1", "peatükk 4.3", "tabel 2.1",
        "joonis 3.4", "lisa 1.2",
        # Inflected, abbreviated, glued, after the number, and listed.
        "Vt lepingu punktis 3.7.", "Sätestatud §3.7 alusel.", "lõikes 2.7",
        "lg 2.7", "lg. 2.7", "p. 3.7", "peatükis 4.7", "ptk 4.7",
        "jaotises 3.7", "tabelis 2.7", "joonisel 3.7", "lisas 1.7", "osas 2.7",
        "nr 3.7", "vt 3.7 punktis", "vt 3.7 lõikes", "punktid 3.2, 3.7 ja 4.7",
        "§ 3.2-3.7", "(punkt 3.7)", "Tabel 2.7. Tulemused", "Loeng on ruumis 3.17.",
        "lepingu punkti 3.7 alusel",
        # A numbered heading.
        "3.7 Tulemused",
        "Sissejuhatus\n3.7 Tulemused",
    ])


def versions_are_skipped() -> None:
    print("decimal-separator: software versions")
    expect_clean([
        "Python 3.12", "versioon 2.4", "v1.2", "iOS 17.2",
        "Python 3.7 on kiire.", "Kasutan Python 3.13 versiooni.",
        "macOS 14.7", "Windows 10.7", "versioonis 2.7", "ver 2.7", "v 2.7",
        "Versioon: 2.7", "Python 3.12 ja 3.13", "3.12.1", "192.168.1.1",
    ])


def english_decimals_still_flag() -> None:
    print("decimal-separator: English decimals still flagged")
    expect_flags({
        "Hind on 1500.50 eurot": [("decimal-separator", "1500.50", "1500,50")],
        "3.14": [("decimal-separator", "3.14", "3,14")],
        "kasv oli 2.5%": [("decimal-separator", "2.5", "2,5")],
        "0.75 liitrit": [("decimal-separator", "0.75", "0,75")],
        "12.5 km": [("decimal-separator", "12.5", "12,5")],
        "umbes 3.7 miljonit": [("decimal-separator", "3.7", "3,7")],
        "See maksis 3.14 eurot.": [("decimal-separator", "3.14", "3,14")],
        # Previously missed: a decimal at a sentence end.
        "Pi on 3.14.": [("decimal-separator", "3.14", "3,14")],
        "Pi on 3.14!": [("decimal-separator", "3.14", "3,14")],
        "Pi: 3.14": [("decimal-separator", "3.14", "3,14")],
        # A unit beats every skip: a section word, a date, a clock range.
        "Lisa 1.5 liitrit vett.": [("decimal-separator", "1.5", "1,5")],
        "Pilet maksab 14.05 eurot.": [("decimal-separator", "14.05", "14,05")],
        "1.25-1.50 eurot": [("decimal-separator", "1.25", "1,25"),
                            ("decimal-separator", "1.50", "1,50")],
        "kella 3.50 euroga": [("decimal-separator", "3.50", "3,50")],
        "€3.50": [("decimal-separator", "3.50", "3,50")],
        "EUR 3.50": [("decimal-separator", "3.50", "3,50")],
        "temperatuur oli 3.7 kraadi": [("decimal-separator", "3.7", "3,7")],
        "2.5GB": [("decimal-separator", "2.5", "2,5")],
        # After a number, punkt is a score, not a clause.
        "Keskmine hinnang oli 3.67 punkti.": [("decimal-separator", "3.67", "3,67")],
        "Indeks tõusis 3.7 punktini.": [("decimal-separator", "3.7", "3,7")],
        # A common word opening the sentence is no product name.
        "Tulemus 3.7 on hea.": [("decimal-separator", "3.7", "3,7")],
        # Neither a clock range nor joined to a skipped number.
        "kasv 3.14-lt 3.17-le": [("decimal-separator", "3.14", "3,14"),
                                 ("decimal-separator", "3.17", "3,17")],
        "Ostsin kella. 3.7 on hea": [("decimal-separator", "3.7", "3,7")],
        "See maksis 3.14 eurot ja linnas elab 1,500,000 inimest.": [
            ("decimal-separator", "3.14", "3,14"),
            ("thousands-separator", "1,500,000", "1 500 000"),
        ],
    })


def issue_shape() -> None:
    print("issue shape")
    r = server.check_numbers("Hind 3.14 ja 1,500,000.50 eurot.")
    check("result is issues and summary_estonian",
          set(r) == {"issues", "summary_estonian"}, str(sorted(r)))
    check("every issue keeps text, position, rule, rule_estonian, suggestion",
          all(set(i) == {"text", "position", "rule", "rule_estonian", "suggestion"}
              for i in r["issues"]), str(r["issues"]))
    check("issues come in text order",
          [i["position"] for i in r["issues"]] == sorted(i["position"] for i in r["issues"]),
          str(r["issues"]))


single_comma_group_is_a_decimal()
unambiguous_thousands_still_flag()
times_are_skipped()
dates_are_skipped()
section_numbers_are_skipped()
versions_are_skipped()
english_decimals_still_flag()
issue_shape()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall check_numbers tests passed")
