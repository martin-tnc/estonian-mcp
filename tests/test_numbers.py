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

4. Reading context brings misfires of its own, pinned below: an EKI clause
   number with its period (4.13. Tellija tasub), a cue on another line, a
   measure or a label in capitals (pH 7.4, KOKKU 1500.50), kell the watch
   (Kella aku kestab 2.5 päeva), a ratio (2.5 osa liiva), a recipe unit
   (0.5 tl), a currency code (CHF 12.50), a midnight hour (00.30), a race
   time (1.47,58), a Markdown heading, an inflected product name (iOS-i).

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


def clause_numbers_with_a_period_are_skipped() -> None:
    print("decimal-separator: EKI clause numbers with a period after them")
    expect_clean([
        "4. Poolte kohustused\n"
        "4.12. Töövõtja kohustub tööd tegema hoolikalt.\n"
        "4.13. Tellija tasub arve 14 päeva jooksul.\n"
        "4.14. Pooled hoiavad konfidentsiaalset teavet.\n"
        "4.15. Leping jõustub allkirjastamisel.\n"
        "4.16. Vaidlused lahendatakse läbirääkimiste teel.",
        "Sisukord\n4.13. Kokkuvõte\n4.14. Lisad",
        "Vastavalt 4.13. punktile on tellija kohustatud maksma.",
        "Leping lõpeb. 4.13. Tellija tasub arve.",
        "(vt 4.13.)",
        "punktid 4.13., 4.14. ja 4.15.",
        "4.13.-4.15. punktid",
        "## 4.13. Kokkuvõte",
    ])
    # A sentence-final decimal still flags: a capital or a quote follows.
    expect_flags({
        "Hind tõusis 4.13. Seejärel langes.": [("decimal-separator", "4.13", "4,13")],
        "Pi on 3.14.” ütles ta.": [("decimal-separator", "3.14", "3,14")],
    })


def markdown_headings_are_skipped() -> None:
    print("decimal-separator: Markdown headings and quotes")
    expect_clean([
        "## 3.7 Tulemused",
        "### 4.13 Kokkuvõte ja järeldused",
        "> 3.7 Tulemused",
    ])


def only_the_numbers_own_line_is_read() -> None:
    print("decimal-separator: no cue is read across a line break")
    expect_flags({
        "Mõõtmistulemused:\n4.37\nKeskmine väärtus jäi normi piiresse.":
            [("decimal-separator", "4.37", "4,37")],
        "Keskmine hinne oli 3.67\nTabel 2 näitab jaotust.":
            [("decimal-separator", "3.67", "3,67")],
        "Hinnang 3.67\nOsa vastajaid ei vastanud.":
            [("decimal-separator", "3.67", "3,67")],
        "Andmed on esitatud tabelis\n0.87 oli mudeli täpsus.":
            [("decimal-separator", "0.87", "0,87")],
    })


def measures_and_capital_labels_still_flag() -> None:
    print("decimal-separator: a measure or a label in capitals is no product")
    expect_flags({
        "Vere pH 7.4 on normaalne.": [("decimal-separator", "7.4", "7,4")],
        "Patsiendi BMI 31.2 viitab rasvumisele.": [("decimal-separator", "31.2", "31,2")],
        "Eesti Panga prognoosi järgi kasvab SKP 2.7 võrra.":
            [("decimal-separator", "2.7", "2,7")],
        "Mudeli AUC 0.87 oli parim.": [("decimal-separator", "0.87", "0,87")],
        # Both ends of a range share the measure, though both are clock-shaped.
        "pH 7.35-7.45 on normaalne vahemik.": [("decimal-separator", "7.35", "7,35"),
                                               ("decimal-separator", "7.45", "7,45")],
        "KOKKU 1500.50": [("decimal-separator", "1500.50", "1500,50")],
        "ARVE SUMMA 249.90": [("decimal-separator", "249.90", "249,90")],
        "Hind KM-ga 49.90": [("decimal-separator", "49.90", "49,90")],
        # A closing quote ends the sentence, so Keskmine is no mid-sentence name.
        "Ta ütles: „Kõik on hästi.” Keskmine 3.67 jäi siiski alla ootuste.":
            [("decimal-separator", "3.67", "3,67")],
        "Ta ütles: „Kõik on hästi.“ Keskmine 3.67 jäi siiski alla ootuste.":
            [("decimal-separator", "3.67", "3,67")],
    })
    # Product acronyms keep their versions.
    expect_clean([
        "Seadmel on USB 3.0 port ja HDMI 2.1 väljund.",
        "PHP 8.2 toetab seda.",
    ])


def kell_needs_a_clock_time() -> None:
    print("decimal-separator: kell the watch is no time cue")
    expect_flags({
        "Kella aku kestab 2.5 päeva.": [("decimal-separator", "2.5", "2,5")],
        "Uus kell on 2.5 korda kallim.": [("decimal-separator", "2.5", "2,5")],
        "Kellad maksavad 49.90 kuni 99.90.": [("decimal-separator", "49.90", "49,90"),
                                              ("decimal-separator", "99.90", "99,90")],
        "Kella hind oli 49.99.": [("decimal-separator", "49.99", "49,99")],
        "Kell maksis 49.90.": [("decimal-separator", "49.90", "49,90")],
        # Clock-shaped, but hind between kell and the number is no filler.
        "Kella hind oli 12.40.": [("decimal-separator", "12.40", "12,40")],
    })


def ratios_and_recipe_units_still_flag() -> None:
    print("decimal-separator: osa after a number is a ratio, tl and sl are units")
    expect_flags({
        "Sega 1 osa tsementi ja 2.5 osa liiva.": [("decimal-separator", "2.5", "2,5")],
        "Võta 1.5 osa jahu.": [("decimal-separator", "1.5", "1,5")],
        "Sega 1 osa äädikat ja 3.5 osa vett.": [("decimal-separator", "3.5", "3,5")],
        "Lisa 0.5 tl soola ja 1.5 sl suhkrut.": [("decimal-separator", "0.5", "0,5"),
                                                 ("decimal-separator", "1.5", "1,5")],
        "Lisa 0.5 kl suhkrut.": [("decimal-separator", "0.5", "0,5")],
        "Lisa 2.5 klaasi jahu.": [("decimal-separator", "2.5", "2,5")],
    })
    expect_clean(["aruande 3.2 osas"])


def currency_codes_still_flag() -> None:
    print("currency codes, spaced or glued")
    expect_flags({
        "Hind on CHF 12.50 inimese kohta.": [("decimal-separator", "12.50", "12,50")],
        "Hind on SEK 49.90.": [("decimal-separator", "49.90", "49,90")],
        "Hind on EUR3.50.": [("decimal-separator", "3.50", "3,50")],
        "Laenusumma USD1,500,000 tagastatakse.":
            [("thousands-separator", "1,500,000", "1 500 000")],
    })


def clock_and_race_times_are_skipped() -> None:
    print("decimal-separator: midnight, colon and race times")
    expect_clean([
        "Ööbuss väljub 00.30.",
        "Kell on kolmveerand üks öösel ehk 00.45.",
        "Ta lõpetas ajaga 2:08.24.",
        "Ta jooksis 800 meetrit ajaga 1.47,58.",
        "Lõpptulemus\n1.47,58",
        # The suggestion 1,500 would have made this 1,500,50.
        "1.500,50 eurot",
    ])
    # Without the leading zero, 0.30 is a decimal.
    expect_flags({"Väärtus oli 0.30.": [("decimal-separator", "0.30", "0,30")]})


def inflected_and_compound_version_words_are_skipped() -> None:
    print("decimal-separator: inflected product names, compound version words")
    expect_clean([
        "Toetame iOS-i 17.2 ja uuemaid.",
        "Uuenda Chrome'i 120.0 peale.",
        "Projekt vajab Node.js 18.19 või uuemat.",
        "Rakendus töötab .NET 8.0 peal.",
        "Seade uuendati tarkvaraversioonile 2.17.",
        "Püsivaraversioon 2.17 parandab vea.",
        "Lisatabelis 3.2 on andmed.",
    ])
    # A compound ending in punkt or osa is an amount, not a clause.
    expect_flags({
        "Keemispunkt 78.37 on kõrge.": [("decimal-separator", "78.37", "78,37")],
        "Omaosa 249.90 tasub klient.": [("decimal-separator", "249.90", "249,90")],
    })


single_comma_group_is_a_decimal()
unambiguous_thousands_still_flag()
times_are_skipped()
dates_are_skipped()
section_numbers_are_skipped()
versions_are_skipped()
english_decimals_still_flag()
clause_numbers_with_a_period_are_skipped()
markdown_headings_are_skipped()
only_the_numbers_own_line_is_read()
measures_and_capital_labels_still_flag()
kell_needs_a_clock_time()
ratios_and_recipe_units_still_flag()
currency_codes_still_flag()
clock_and_race_times_are_skipped()
inflected_and_compound_version_words_are_skipped()
issue_shape()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall check_numbers tests passed")
