"""Tests for `check_numbers`.

0.8.0 read no context: every d.d was an English decimal and every comma
group a thousands separator, so it flagged times, dates, section and
version numbers and Estonian decimals (1,250 kg), and it missed every
decimal before a sentence-final period (Pi on 3.1416.). The rules now in
server.py skip a number on a bounded window around it, and the bar is that
the tool does at least as well as 0.8.0 on every input. The trade-offs the
design accepts are pinned here as such, each with its reason, so a change
that moves one shows up.

Run via:

    uv run python tests/test_numbers.py
"""
from __future__ import annotations

import sys
import time
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


def decimals(text: str) -> list[str]:
    return [t for rule, t, _ in found(text) if rule == "decimal-separator"]


def expect_clean(cases: list[str]) -> None:
    for text in cases:
        got = found(text)
        check(f"clean: {text!r}", got == [], str(got))


def expect_decimals(cases: dict[str, list[str]]) -> None:
    for text, want in cases.items():
        got = decimals(text)
        check(f"flags {want}: {text!r}", got == want, f"got {got}")


def thousands() -> None:
    print("thousands-separator")
    # One group is an Estonian decimal. Trade-off: 437,811 inimest is missed.
    expect_clean(["1,250 kg", "Pi on umbes 3,142", "Kaal oli 1,500.",
                  "Päeval 14.05.2026 maksis pi umbes 3,14.",
                  "Linnas elab 437,811 inimest."])
    cases = {
        "Linnas elab 1,500,000 inimest.": [("thousands-separator", "1,500,000", "1 500 000")],
        "Linnas elab 1,500,000.": [("thousands-separator", "1,500,000", "1 500 000")],
        "Laenusumma USD1,500,000 tagastatakse.":
            [("thousands-separator", "1,500,000", "1 500 000")],
        # The decimal is converted too, and 500.50 is no issue of its own.
        "Hind oli 1,500.50 eurot.": [("thousands-separator", "1,500.50", "1 500,50")],
        "Kokku 1,500,000.50 eurot.":
            [("thousands-separator", "1,500,000.50", "1 500 000,50")],
    }
    for text, want in cases.items():
        got = found(text)
        check(f"flags {want}: {text!r}", got == want, f"got {got}")
    r = server.check_numbers("Kokku 1,500,000.50 eurot.")
    check("1,500,000.50 is reported at its start",
          [i["position"] for i in r["issues"]] == [6], str(r["issues"]))


def kell() -> None:
    print("rule 1: a time after kell or kl")
    expect_clean(["kell 10.20", "Kell 10.20 algab koosolek.", "kella 10.20-ni",
                  "kellaajal 10.20", "kl 9.20", "kl. 9.20"])
    # Only the word right before counts: kell the watch is no cue.
    expect_decimals({
        # kelle (whose) is a form of kes.
        "Isik, kelle 2.5 aastane karistus lõppes, vabanes.": ["2.5"],
        "Kelle 2.5 pakki jäi alles?": ["2.5"],
        "Kella aku kestab 2.5 päeva.": ["2.5"],
        "Uus kell on 2.5 korda kallim.": ["2.5"],
        "Kellad maksavad 49.90 kuni 99.90.": ["49.90", "99.90"],
        "Kell maksis 49.90.": ["49.90"],
    })


def time_ranges() -> None:
    print("rule 2: a time range, both ends")
    expect_clean(["10.30-12.00", "10.20-12.40", f"10.20 {EN_DASH} 12.40",
                  f"kell 9.15{EN_DASH}17.00", "kell 9.20-17.40", "10.30-12.00."])
    # Trade-off: a confidence interval has the same shape.
    expect_clean(["usaldusvahemik 1.05-1.20"])
    expect_decimals({
        # Not a range: the right end is earlier, a part has one digit.
        "kasv 3.14-lt 3.17-le": ["3.14", "3.17"],
        "intervall 0.5-1.5": ["0.5", "1.5"],
        # A unit after the range flags both ends.
        "1.25-1.50 eurot": ["1.25", "1.50"],
        "Hind on EUR 1.25-1.50": ["1.25", "1.50"],
    })


def section_words() -> None:
    print("rule 3: a section or version number after its word")
    expect_clean([
        "punkt 3.2", "§ 3.2", "Sätestatud §3.7 alusel.", "lõige 2.1", "lõikes 2.7",
        "peatükk 4.3", "peatükis 4.7", "jaotises 3.7", "tabel 2.1", "Tabel 2.7: Tulemused",
        "joonisel 3.4", "versioonis 2.7", "Versioon: 2.7", "paragrahvi 3.7",
        "artikli 3.7", "lisa 1.2", "(punkt 3.7)", "lepingu punkti 3.7 alusel",
        "lg 2.7", "lg. 2.7", "p. 3.7", "ptk 4.7", "nr 3.7", "v 2.7", "ver 2.7",
        # Inflected abbreviations.
        "Vastavalt lepingu p-s 5.3 sätestatule on tellijal õigus leping üles öelda.",
        "Lõike 2.1 kohaselt kohaldatakse lg-s 2.3 nimetatud tähtaega.",
        "Töövõtja vastutab ptk-s 4.2 kirjeldatud kohustuste eest.",
        "Vt lepingu p-le 4.3 lisatud tingimusi.", "§-s 3.2",
    ])
    # Limits: lowercase lisa is an imperative too, and a word that merely
    # starts with a section word is a cue (punkte, joonistasin).
    expect_clean(["Tainale lisa 0.5 pakki pärmi.", "Ta sai punkte 8.5 ja võitis.",
                  "Joonistasin 2.5 tunniga pildi."])
    expect_decimals({
        # Only lisa as written: Lisa is mostly the imperative "add", lisas
        # the past tense "added".
        "Lisa 2.5 pakki võid ja sega.": ["2.5"],
        "Ringkonnakohus lisas 1.5 aastat vangistust.": ["1.5"],
        "Kokk lisas 1.5 tassi suhkrut.": ["1.5"],
        "lisas 1.7": ["1.7"],
        "Lisa 0.5 pakki pärmi ja 1.5 klaasi sooja piima.": ["0.5", "1.5"],
        # A unit beats a section word: lowercase lisa is an imperative too.
        "Sega ja lisa 0.5 tl soola.": ["0.5"],
        # Only the word right before counts (limit: the list goes on).
        "Vastavalt p-dele 3.2 ja 3.4 tasub tellija ettemaksu.": ["3.4"],
        "vt 3.7 punktis": ["3.7"],
        # Words that merely start like lisa.
        "lisaks 2.5 miljonit": ["2.5"],
    })


def glued_versions() -> None:
    print("rule 4: a version glued to v or to letters and a hyphen")
    expect_clean(["v1.2", "V2.4", "(v1.2)", "Kasutasime mudelit GPT-3.5 ja hiljem GPT-4.1.",
                  "Võrdlesime mudeleid GPT-4.5 ja Llama-3.1."])
    # Other glued letters are no version.
    expect_decimals({"Mõõtsime pH7.4 ja pO2 12.5 kPa.": ["7.4", "12.5"],
                     "Suumi x2.5 suurendusega.": ["2.5"], "2.5GB": ["2.5"]})


def product_names() -> None:
    print("rule 5: a version after a product name")
    expect_clean(["Kasutan Python 3.13 versiooni.", "Projekt vajab Node.js 18.19 või uuemat.",
                  "Uuenda Chrome'i 120.0 peale.", "Andmed on MySQL 8.4 baasis."])
    expect_decimals({
        # Vabamorf knows place names: no product.
        "Sademeid oli Pärnus 12.3, Tartus 8.7 ja Narvas 5.4 mm.": ["12.3", "8.7", "5.4"],
        "Töötuse määr oli Eestis 6.4 ja Soomes 7.8 protsenti.": ["6.4", "7.8"],
        # The sentence's first word, a closing quote before it included.
        "Python 3.7 on kiire.": ["3.7"],
        "Tulemus 3.7 on hea.": ["3.7"],
        "Ta ütles: „Kõik on hästi.” Keskmine 3.67 jäi siiski alla ootuste.": ["3.67"],
        "Analüütik ütles: „Turud olid punases.“ Nasdaq 2.1 ja S&P 1.8 protsendiga miinuses.":
            ["2.1", "1.8"],
        "„Kas turud langevad?“ Nasdaq 2.1 langes.": ["2.1"],
        # All capitals is a measure or a label more often than a product.
        "Patsiendi BMI 31.2 viitab rasvumisele.": ["31.2"],
        "Mudeli AUC 0.87 oli parim.": ["0.87"],
        "Eesti Panga prognoosi järgi kasvab SKP 2.7 võrra.": ["2.7"],
        "Šansside suhe oli OR 1.83 ja riskisuhe HR 2.41 kontrollrühmas.": ["1.83", "2.41"],
        "Keskmine 3.84 (SD 0.92) oli kõrgem kui kontrollrühmas.": ["3.84", "0.92"],
        "Hind on CHF 12.50 inimese kohta.": ["12.50"],
        "KOKKU 1500.50": ["1500.50"],
        "ARVE SUMMA 249.90": ["249.90"],
        "Hind KM-ga 49.90": ["49.90"],
        # Lowercase first: pH is a measure (limit: so is iOS, still flagged).
        "Vere pH 7.4 on normaalne.": ["7.4"],
        "Toetame iOS-i 17.2 ja uuemaid.": ["17.2"],
        # A unit after the number beats the name.
        "Kasutan Python 3.8 korda kiiremini.": ["3.8"],
    })


def dates() -> None:
    print("rule 6: a date, day 1-31 and a two-digit month")
    expect_clean(["Kohtume 14.05", "Kohtume 14.05.", "Kohtume 14.05.2026",
                  "Kohtume 1.05", "Tähtaeg on 31.12 ja 1.01.", "03.04 kell 9"])
    # Trade-off: a decimal of that shape with no unit is skipped too.
    expect_clean(["Reproduktsioonikordaja oli 1.05 ja hakkas seejärel langema."])
    expect_decimals({
        "Pilet maksab 14.05 eurot.": ["14.05"],
        "Indeks tõusis 1.10 punkti võrra.": ["1.10"],
        "Rõhk oli 1.10 bar.": ["1.10"],
        "Hind on €14.05": ["14.05"],
        "Kohtume 14.5 ja": ["14.5"],
    })


def clause_numbers() -> None:
    print("rule 7: a clause number opening a line")
    expect_clean([
        "4. Poolte kohustused\n"
        "4.12. Töövõtja kohustub tööd tegema hoolikalt.\n"
        "4.13. Tellija tasub arve 14 päeva jooksul.\n"
        "4.14. Pooled hoiavad konfidentsiaalset teavet.\n"
        "4.15. Leping jõustub allkirjastamisel.\n"
        "4.16. Vaidlused lahendatakse läbirääkimiste teel.",
        "Sisukord\n4.13. Kokkuvõte\n4.14. Lisad",
        "Tingimused:\n- 4.73. Tellija tasub arve.",
        "## 3.7 Tulemused", "### 4.13 Kokkuvõte ja järeldused", "## 4.73. Kokkuvõte",
        # A period after the number and a lowercase word: never a candidate.
        "Vastavalt 4.73. punktile on tellija kohustatud maksma.",
        "punktid 4.13., 4.14. ja 4.15.", "(vt 4.73.)",
    ])
    # A heading without # looks like a data row, so both are flagged.
    expect_decimals({
        "3.7 Tulemused": ["3.7"],
        "Tulemused:\n9.58 Usain Bolt\n9.69 Tyson Gay": ["9.58", "9.69"],
        "Inflatsioon riigiti:\n3.9 Eesti\n2.7 Läti\n2.1 Leedu": ["3.9", "2.7", "2.1"],
        "Mõõtmistulemused:\n4.37\nKeskmine väärtus jäi normi piiresse.": ["4.37"],
        "## 3.7 tulemused": ["3.7"],
        # No cue is read across a line break.
        "Keskmine hinne oli 3.67\nTabel 2 näitab jaotust.": ["3.67"],
        "Andmed on esitatud tabelis\n0.87 oli mudeli täpsus.": ["0.87"],
        "Tabel\n10.72 Mart Tamm\n10.85 Jaan Kask": ["10.72", "10.85"],
    })


def comma_tails() -> None:
    print("rule 8: a comma part after the number")
    expect_clean(["Ta jooksis 800 meetrit ajaga 1.47,58.", "Lõpptulemus\n1.47,58",
                  "1.500,50 eurot", "Ta läbis 5000 m ajaga 13.47,32 ja 10 000 m ajaga 28.21."])
    expect_decimals({"Väärtused 1.5, 2.5": ["1.5", "2.5"]})


def units() -> None:
    print("a unit, currency, per cent or multiplier flags the number")
    expect_decimals({
        "Hind on 1500.50 eurot": ["1500.50"],
        "kasv oli 2.5%": ["2.5"],
        "Tõus 2.5-3.5 %": ["2.5", "3.5"],
        "0.75 liitrit": ["0.75"],
        "umbes 3.7 miljonit": ["3.7"],
        "€3.50": ["3.50"],
        "EUR 3.50": ["3.50"],
        "kella 3.50 euroga": ["3.50"],
        "Mängija sai 8.45 punkti.": ["8.45"],
        "Sprinter jooksis 100 m ajaga 10.15 s.": ["10.15"],
        "Wi-Fi töötab sagedusel 2.45 GHz.": ["2.45"],
        "Pinge on 12.00 V ja vool 1.05 A.": ["12.00", "1.05"],
        "Ping oli keskmiselt 12.45 ms.": ["12.45"],
        "Lisa 0.5 tl soola ja 1.5 sl suhkrut.": ["0.5", "1.5"],
        "Lisa 0.5 kl suhkrut.": ["0.5"],
        "Lisa 1.5 küüslauguküünt ja 0.25 tl pipart.": ["1.5", "0.25"],
        # A squared or cubed unit is the unit.
        "Rõdu pindala on 4.08 m² ja see on klaasitud.": ["4.08"],
        "Veekulu oli eelmisel kuul 3.12 m³.": ["3.12"],
        "Maatüki suurus on 1.12 km².": ["1.12"],
        "Ristlõige 2.05 mm² on liiga väike.": ["2.05"],
        "Toa pindala on 10.12 m², köögil 7.5 m².": ["10.12", "7.5"],
        "Pindala 4.08 m2.": ["4.08"],
    })


def sentence_ends() -> None:
    print("a number before a sentence-final period")
    expect_decimals({
        "Kasv oli 2.5.": ["2.5"],
        "Pi on 3.1416.": ["3.1416"],
        "Mõõtetulemused olid 1.30, 1.47, 1.52 ja 1.61.": ["1.30", "1.47", "1.52", "1.61"],
        "Hind tõusis 4.73. Seejärel langes.": ["4.73"],
        "Hind oli 1500.50.": ["1500.50"],
        "Hind on €12.50.": ["12.50"],
        "Pi on 3.14!": ["3.14"],
    })
    # Where 0.8.0 flagged nothing, a time's shape or a word with a capital
    # stays clean: the product rule misses iOS (lowercase) and Android (in
    # the lexicon), and they would be new false hits.
    expect_clean(["Ööbuss väljub 00.30.", "Kell on kolmveerand üks öösel ehk 00.45.",
                  "Lend AY1022 väljub 6.55.", "Ta lõpetas 10 km ajaga 32.15.",
                  "Ta lõpetas ajaga 2:08.24.", "Seade uuendati tarkvaraversioonile 2.17.",
                  "punktid 4.13., 4.14. ja 4.15.", "Telefonis on iOS 17.2.",
                  "Kasutame Android 4.4.", "Kasutame USB 3.0.",
                  # Limits: pi to two places has a time's shape, Narvas a capital.
                  "Pi on 3.14.", "Patsiendi BMI 31.2."])
    expect_decimals({
        "Etendus algab 19.10 ja lõpeb 21.40.": [],
        "Buss väljub peatusest 8.47 ja jõuab kohale 9.22.": ["8.47"],
        "Sademeid oli Pärnus 12.3, Tartus 8.7 ja Narvas 5.1.": ["12.3", "8.7"],
        "Töötuse määr oli Eestis 6.4 ja Soomes 7.8.": ["6.4"],
        # Limits, where 0.8.0 flagged nothing: a date with a one-digit
        # month, a version after a verb, a clause number inside a line.
        "Tähtaeg on 1.9.": ["1.9"],
        "Uus versioon on 3.2.": ["3.2"],
        "Lepingu punktid: 4.1. Tellija tasub arve. 4.2. Töövõtja annab töö üle.": ["4.2"],
    })


def still_flagged() -> None:
    print("what 0.8.0 flagged and no rule explains stays flagged")
    expect_decimals({
        "3.14": ["3.14"],
        "Pi: 3.14": ["3.14"],
        "See maksis 3.14 eurot.": ["3.14"],
        "Ostsin kella. 3.7 on hea": ["3.7"],
        "Sega 1 osa tsementi ja 2.5 osa liiva.": ["2.5"],
        "Maavärin tugevusega 6.30 magnituudi raputas Jaapanit.": ["6.30"],
        "Vastajate keskmine hinnang oli 3.45 (SD 0.83).": ["3.45", "0.83"],
        "Rühmade erinevus oli statistiliselt oluline (t = 2.15, p = 0.04).": ["2.15", "0.04"],
        "| Aasta | Kasv |\n| 2022 | 2.15 |\n| 2023 | 1.45 |": ["2.15", "1.45"],
        # Limit: a bare time; only kell tells it from a decimal.
        "Koosolek algab 10.30 ja kestab tund.": ["10.30"],
        "Lennuk maandub 23.55, nii et jõuan koju alles pärast südaööd.": ["23.55"],
    })
    got = found("See maksis 3.14 eurot ja linnas elab 1,500,000 inimest.")
    check("both rules in one text", got == [
        ("decimal-separator", "3.14", "3,14"),
        ("thousands-separator", "1,500,000", "1 500 000"),
    ], str(got))


def issue_shape() -> None:
    print("issue shape")
    r = server.check_numbers("Hind 3.67 ja 1,500,000.50 eurot.")
    check("result is issues and summary_estonian",
          set(r) == {"issues", "summary_estonian"}, str(sorted(r)))
    check("every issue keeps text, position, rule, rule_estonian, suggestion",
          all(set(i) == {"text", "position", "rule", "rule_estonian", "suggestion"}
              for i in r["issues"]), str(r["issues"]))
    check("issues come in text order",
          [i["position"] for i in r["issues"]] == sorted(i["position"] for i in r["issues"]),
          str(r["issues"]))


def linear_time() -> None:
    print("linear time on 100,000 characters")
    texts = {f"{unit!r} repeated": (unit * (100_000 // len(unit) + 1))[:100_000]
             for unit in ("1.5-", f"3.7 {EN_DASH} ", "10.20-", "ja Xyz 1.5 ",
                          "4.13. Tellija\n", "kell 10.20-12.30 ", "€14.05 ")}
    # Each new capitalised word costs a lexicon lookup, up to 2 ms for a
    # long compound, so a text gets _NUM_LOOKUPS of them.
    roots = ["maja", "kooli", "aia", "puu", "kivi", "vee", "tee", "linna", "metsa", "auto",
             "raamatu", "laua", "töö", "ilma", "maa", "kala", "lille", "saare", "ase", "osa"]
    words = ("".join(roots[(n * 7919 // 20 ** k) % 20] for k in range(8)).capitalize()
             for n in range(3000))
    unique = "".join(f"ja {w} 1.5 " for w in words)[:100_000]
    texts["unique long compounds"] = unique
    real, calls = server._vabamorf, []

    class Counting:
        def analyze(self, **kwargs):
            calls.append(kwargs["words"])
            return real().analyze(**kwargs)

    server._vabamorf = Counting
    try:
        server.check_numbers(unique)
    finally:
        server._vabamorf = real
    check(f"{len(calls)} lexicon lookups for {unique.count(' 1.5 ')} new words",
          0 < len(calls) <= server._NUM_LOOKUPS, str(len(calls)))
    for label, text in texts.items():
        t = time.perf_counter()
        server.check_numbers(text)
        dt = time.perf_counter() - t
        # 0.8.0 took 0.15 s; a quadratic walk took 30 to 65 s, a lookup
        # per word 2 to 5 s. Locally the worst is 0.25 s.
        check(f"{label}: {dt:.2f} s", dt < 2, f"{dt:.2f} s")


thousands()
kell()
time_ranges()
section_words()
glued_versions()
product_names()
dates()
clause_numbers()
comma_tails()
units()
sentence_ends()
still_flagged()
issue_shape()
linear_time()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall check_numbers tests passed")
