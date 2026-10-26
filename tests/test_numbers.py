"""Tests for `check_numbers`.

0.8.0 read no context: every d.d was an English decimal, so it flagged
times, dates, section and version numbers, and it missed every decimal
before a sentence-final period (Pi on 3.1416.). A comma group is the
English thousands separator, written 1250 / 12 500 in Estonian. The rules now in
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
    # 0,125 can only be a decimal, and a two-place decimal is no group.
    expect_clean(["Kurss oli 0,125.", "Päeval 14.05.2026 maksis pi umbes 3,14.",
                  "Aeg 1.47,580 oli rekord."])
    cases = {
        # One group is the English separator unless the writer meant a
        # three-place decimal (the description says to keep it then). EKI
        # writes four digits together and groups from five.
        "Hind on 1,250 eurot.": [("thousands-separator", "1,250", "1250")],
        "Kaal oli 1,500.": [("thousands-separator", "1,500", "1500")],
        "Linnas elab 437,811 inimest.": [("thousands-separator", "437,811", "437 811")],
        "Summa 12,500 eurot.": [("thousands-separator", "12,500", "12 500")],
        "Linnas elab 1,500,000 inimest.": [("thousands-separator", "1,500,000", "1 500 000")],
        "Linnas elab 1,500,000.": [("thousands-separator", "1,500,000", "1 500 000")],
        "Laenusumma USD1,500,000 tagastatakse.":
            [("thousands-separator", "1,500,000", "1 500 000")],
        # The decimal is converted too, and 500.50 is no issue of its own.
        "Hind oli 1,500.50 eurot.": [("thousands-separator", "1,500.50", "1500,50")],
        "Hind oli 12,500.50 eurot.": [("thousands-separator", "12,500.50", "12 500,50")],
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


def tildes(text: str) -> list[tuple[str, str]]:
    return [(t, sug) for rule, t, sug in found(text) if rule == "approximate-tilde"]


def approximate_tilde() -> None:
    print("approximate-tilde: ~ meaning about before a number (EKI Arvukirjutus p 11)")
    nbsp = chr(0xA0)
    cases = {
        "Meeskonnas on ~50 inimest.": [("~50", "u 50")],
        "Laulupeol esines ~40-liikmeline koor.": [("~40", "u 40")],
        "Kestus: ~ 5 km.": [("~ 5", "u 5")],
        "Matk on pikk (~5 km) ja kerge.": [("~5", "u 5")],
        "~200 inimest registreerus esimesel päeval.": [("~200", "Umbes 200")],
        "- ~15 osalejat igas rühmas": [("~15", "Umbes 15")],
        "Eelarve: ~12 000 eurot.": [("~12 000", "u 12 000")],
        "Ootame ~40 kuni ~60 külalist.": [("~40", "u 40"), ("~60", "u 60")],
        "| Osalejaid | ~120 |": [("~120", "u 120")],
        "Vahemaa on ~1,5 km.": [("~1,5", "u 1,5")],
        "Pilet maksab 5000 franki, ~ 120 krooni.": [("~ 120", "u 120")],
        "Osalejad\n\n~ 40 inimest": [("~ 40", "Umbes 40")],
        "Ootame ~50% rohkem külastajaid.": [("~50", "u 50")],
        f"Hind: ~{nbsp}50 eurot": [(f"~{nbsp}50", "u 50")],
        # A * or + opening a line is a bullet like -, not an operator.
        "* ~10 minutit jalutuskäiku kesklinnast": [("~10", "Umbes 10")],
        "+ ~10 minutit jalutuskäiku kesklinnast": [("~10", "Umbes 10")],
        # An indented block is code only after a blank line or the text
        # start and outside a list, so prose around it is still read.
        "    ls ~1\n    git log HEAD~2\nTavatekst ~3 korda.": [("~3", "u 3")],
        "Seletus.\n    jätkub ~5 korda.": [("~5", "u 5")],
        "- Hotell:\n\n    - ~10 minutit": [("~10", "Umbes 10")],
        "Kasuta ``foo`` ja ~5 minutit.": [("~5", "u 5")],
    }
    for text, want in cases.items():
        got = tildes(text)
        check(f"flags {want}: {text!r}", got == want, f"got {got}")
    # EKI writes the tilde between parallel variants, always spaced
    # (mina ~ ma, 2005 ~ 2005. a), so a spaced tilde after a word is left
    # alone. Code, paths, statistics, versions and ranges are not prose.
    for text in [
        "Meeskonnas on u 50 inimest ja ca 30 vabatahtlikku.", "Ruumis oli u. 50 inimest.",
        "Failid on kaustas ~/docs ja ~/Downloads.", "Hind oli ~~50 eurot~~ ja nüüd 40.",
        "Hind oli ~50 eurot~ ja nüüd 40 eurot.", "Mudelis eeldame, et x ~ N(0,1).",
        "Tulemus oli oluline (p ~ 0,05).", "Valemis a ~ 2b on seos lineaarne.",
        "Kood: `x = ~5` annab -6.", "Käsk `git reset HEAD~1` tühistab kande.",
        "```\nx = ~5\ny = ~ 3\n```", "~~~\nls ~1\n~~~", "Nõue on Python ~3.11 või uuem.",
        'Kasuta sõltuvust "lodash": "~4.17.21".', "Vahemik 5~10 on sobiv.",
        "Vahemik 5 ~10 on sobiv.", "Temperatuur oli 20 ~ 25 kraadi.",
        "Aadress on https://example.org/~50/leht.", "Fail PROGRA~1 asub juurkaustas.",
        "Vesi on H~2~O.", "Kirjutatakse 25aastane ~ 25-aastane.",
        "Aastal 2005 ~ 2005. aastal ~ 2005. a toimus üritus.",
        "Kirjutatakse 1974. aastal\n~ 1974. a ja nii edasi.", "Rööpvormid on mina ~ ma.",
        "Arvutus π ≈ 3,14 on piisav.", "Osalejaid oli ≈50.", "Kurss: 1 € = ~10 ühikut.",
        "Tulemus 50~ oli ootamatu.", "Arv 5 * ~10 on suur.",
        # A double-backtick span and an indented code block are code too.
        "`` ~5 `` on koodis.", "Kood: `` x = ~5 `` ja `` ~7 ``.",
        "Seletus.\n\n    print(~5)", "\tls ~1",
    ]:
        got = tildes(text)
        check(f"no tilde flag: {text!r}", got == [], str(got))
    # A comma or period part after the number belongs to the separator
    # rules, so one number never carries two issues.
    check("~1,250 is a thousands issue only",
          found("Linnas elab ~1,250 inimest.") == [("thousands-separator", "1,250", "1250")],
          str(found("Linnas elab ~1,250 inimest.")))
    check("~1.5 is a decimal issue only",
          found("Kestus ~1.5 tundi.") == [("decimal-separator", "1.5", "1,5")],
          str(found("Kestus ~1.5 tundi.")))


def expect_found(cases: dict[str, list[tuple[str, str, str]]]) -> None:
    for text, want in cases.items():
        got = found(text)
        check(f"finds {want}: {text!r}", got == want, f"got {got}")


def month_year() -> None:
    print("month-year-digits: a month and year in digits is a date (EKI Arvukirjutus p 33)")
    expect_found({
        "Tööde lõpp on 09.2016.": [("month-year-digits", "09.2016", "sept 2016")],
        "Tähtaeg on 11.2027.": [("month-year-digits", "11.2027", "nov 2027")],
        "| 03.2011 | 07.2013 |": [("month-year-digits", "03.2011", "märts 2011"),
                                  ("month-year-digits", "07.2013", "juuli 2013")],
        # Both ends get the hint and the range is left alone: in words EKI
        # spaces the dash (aprill 2008 - august 2009).
        "04.2008 - 08.2009 raamatupidaja": [("month-year-digits", "04.2008", "apr 2008"),
                                           ("month-year-digits", "08.2009", "aug 2009")],
        "10.2017 - praeguseni": [("month-year-digits", "10.2017", "okt 2017")],
        # A unit, currency or math sign makes it a number again.
        "Kaugus oli 11.2027 m.": [("decimal-separator", "11.2027", "11,2027")],
        "Hind 1.2019 eurot": [("decimal-separator", "1.2019", "1,2019")],
        "Tulemus oli t = 2.1987 ja p alla 0,05.": [("decimal-separator", "2.1987", "2,1987")],
        "Mõõtsime 1.1950 - 1.2050 m.": [("decimal-separator", "1.1950", "1,1950"),
                                        ("decimal-separator", "1.2050", "1,2050")],
        # 10 to 12 has no leading zero to mark a month: a rate word or a
        # currency pair earlier in the clause makes it a decimal.
        "Valuutakurss EUR/SEK oli eile 11.2050.": [("decimal-separator", "11.2050", "11,2050")],
        "USD/SEK kurss kerkis 10.1985 tasemele.": [("decimal-separator", "10.1985", "10,1985")],
        "Rootsi krooni kurss oli 11.2050.": [("decimal-separator", "11.2050", "11,2050")],
        "Valuutakurss: 11.2050": [("decimal-separator", "11.2050", "11,2050")],
        "Koefitsiendid olid 0.2019, 10.2019 ja 11.1998.": [
            ("decimal-separator", "0.2019", "0,2019"), ("decimal-separator", "10.2019", "10,2019"),
            ("decimal-separator", "11.1998", "11,1998")],
        "Pikkuskraad 10.2041 ja laiuskraad 59.4370.": [
            ("decimal-separator", "10.2041", "10,2041"), ("decimal-separator", "59.4370", "59,4370")],
        "Kaalutud keskmine oli 10.2015 ja mediaan 9.8.": [
            ("decimal-separator", "10.2015", "10,2015"), ("decimal-separator", "9.8", "9,8")],
        # A date word next to it, a zero-padded month or no rate word keeps
        # the date; the clause ends at a sentence end.
        "Keskmine palk seisuga 10.2023 oli 1800 eurot.": [
            ("month-year-digits", "10.2023", "okt 2023")],
        "Kurss oli 09.2016.": [("month-year-digits", "09.2016", "sept 2016")],
        "Kursus algab 10.2027.": [("month-year-digits", "10.2027", "okt 2027")],
        "Keskmine hinne oli 3.67. Kursus algab 10.2027.": [
            ("decimal-separator", "3.67", "3,67"), ("month-year-digits", "10.2027", "okt 2027")],
    })
    # A one-digit month may be an exchange rate (1.2050): neither a decimal
    # nor a date is claimed. In code it is program output.
    expect_clean(["Töötasin ettevõttes alates 9.2019 kuni praeguseni.",
                  "Periood 1.2019 kuni 3.2020.",
                  "Kasuta `date +%m.%Y`, mis annab näiteks `04.2017`.", "```\n04.2017\n```"])


def range_spacing() -> None:
    print("range-spacing: no spaces around a range dash between plain numbers")
    expect_found({
        "Töötasin seal aastatel 2020 - 2024.": [("range-spacing", "2020 - 2024", "2020-2024")],
        "2015 - 2019 projektijuht, arendusosakond": [("range-spacing", "2015 - 2019", "2015-2019")],
        "Laat toimub 3.06.2027 - 5.06.2027 Pärnus.": [
            ("range-spacing", "3.06.2027 - 5.06.2027", "3.06.2027-5.06.2027")],
        "Ravi kestab 5 - 10 päeva.": [("range-spacing", "5 - 10", "5-10")],
        "Ootame 10 - 15 inimest.": [("range-spacing", "10 - 15", "10-15")],
        "Kursus kestab 3 - 4 kuud.": [("range-spacing", "3 - 4", "3-4")],
        "Vt lk 5 - 9.": [("range-spacing", "5 - 9", "5-9")],
        "Sätestatud §-des 5 - 8.": [("range-spacing", "5 - 8", "5-8")],
        "Vastuvõtt on 10.00 - 12.00 ruumis 101.": [("range-spacing", "10.00 - 12.00", "10.00-12.00")],
        "Kauplus on lahti kell 9 - 17.": [("range-spacing", "9 - 17", "9-17")],
        "Kursus on mõeldud 18 - 25-aastastele.": [("range-spacing", "18 - 25", "18-25")],
        "Hinnatõus oli 5 - 10%.": [("range-spacing", "5 - 10", "5-10")],
        "Kaal on 1,5 - 2,5 kg.": [("range-spacing", "1,5 - 2,5", "1,5-2,5")],
        "Kantselei on suletud 24.12 - 27.12.": [("range-spacing", "24.12 - 27.12", "24.12-27.12")],
        "Projekt kestis 2018- 2021 ja lõppes edukalt.": [("range-spacing", "2018- 2021", "2018-2021")],
        "| 2020 - 2024 | juhataja |": [("range-spacing", "2020 - 2024", "2020-2024")],
        # A plural label, a cue with nothing after it and a quantity noun
        # are no label and value.
        "Lahenda ülesanded 1 - 5 punkti kaupa.": [("range-spacing", "1 - 5", "1-5")],
        "Loe peatükk 3 - 5.": [("range-spacing", "3 - 5", "3-5")],
        "Hind 10 - 15 eurot.": [("range-spacing", "10 - 15", "10-15")],
        "Pakett 1,5 - 2,5 kg.": [("range-spacing", "1,5 - 2,5", "1,5-2,5")],
        # A comitative after a range is no score, and a broad score word
        # (tulemus) counts only among the last three words.
        "Indeks tõusis 1,5 - 2,5 punktiga.": [("range-spacing", "1,5 - 2,5", "1,5-2,5")],
        "Uuringu tulemuste põhjal kestab ravi 5 - 10 päeva.": [("range-spacing", "5 - 10", "5-10")],
        "Teises geimis jäi Eesti taha 18 - 25 punktiga, aga ravi kestab 5 - 10 päeva.": [
            ("range-spacing", "5 - 10", "5-10")],
        # Prose around code is still read.
        "```\nkood\n```\nTöötasin seal aastatel 2020 - 2024.": [
            ("range-spacing", "2020 - 2024", "2020-2024")],
        "Kood `x` ja aastatel 2020 - 2024 töötasin.": [("range-spacing", "2020 - 2024", "2020-2024")],
    })
    # Not ranges, ranges EKI writes otherwise, or ends that contain a space.
    expect_clean([
        "Aastad 2020-2024 olid head.", "10 - 5 = 5", "Ajavahe: 13 - 3 + 9 = 19",
        "Arvuta 12 - 4 ja kirjuta vastus.", "Seis oli 3 - 1.", "Mäng lõppes 1 - 3 külaliste kasuks.",
        "Seis on 1 - 3 kodumeeskonna kahjuks.", "Kodumeeskond - külalised 1 - 3 (0 - 2)",
        "Temperatuur langes -5 - -10 kraadini.", "Tel +372 5555 - 1234",
        "Helista 5123 - 4567, kui tekib küsimusi.", "Kontakt: 5123 - 6789", "- 2020 aruanne valmis",
        "1. - 3. koht jäi meie võistkonnale.", "Eelarve on 9000 - 10 000 eurot.",
        "Palk 1 500 - 2 000 eurot.", "Ta elas 14. XI 1920 - 21. XII 2005 Tartus.",
        "Leping kehtis 2015 - 2019. aastal.", "Õppeaasta 2025 - 2026 algab septembris.",
        "Hooaeg 2019 - 2020 oli edukas.", "Aastad 1990 - 2000 - 2010 näitasid kasvu.",
        "Tulemused: 10,55 - 7,49 - 13,98", "Näitus on lahti 5 - 10 mai.", "Ta töötas 5 - 10 märtsi.",
        "Ajakirja nr 8 - 2009 artikkel", "Metsa tn 87 - 26", "Fail aruanne 2019 - 2020.pptx on kaustas.",
        "Viik 2 - 2.", f"Aastad 2020 {EN_DASH} 2024 olid head.",
        # A singular label noun, its number and a value with a unit or noun:
        # the hyphen stands for a spaced mõttekriips, not "to".
        "Hindamine: ülesanne 1 - 10 punkti, ülesanne 2 - 15 punkti, ülesanne 3 - 25 punkti.",
        "Hinnakiri: pakett 1 - 25 eurot, pakett 2 - 40 eurot.",
        "Hinnakiri\nVariant 1 - 30 €\nVariant 2 - 45 €", "Rühm 1 - 12 last, rühm 2 - 15 last.",
        "Klass 1 - 24 õpilast, klass 2 - 26 õpilast.", "Tuba 1 - 2 voodit, tuba 2 - 3 voodit.",
        "Ruum 1 - 10 kohta, ruum 2 - 20 kohta.",
        "Joonis 2 - 3 peamist põhjust, miks töötajad lahkuvad",
        "Osa 2 - 10 nõuannet algajale aednikule",
        "Episood 4 - 7 harjumust, mis muudavad päeva paremaks",
        "Peatükk 3 - 5 sammu eduka projekti poole",
        # A sports word anywhere in the clause makes a score.
        "Teises geimis jäi Eesti taha 18 - 25 punktiga.",
        "Eesti kaotas geimid 20 - 25 ja 23 - 25 punktiga.",
        # Code, and an expression after =.
        "Arvuta `2020 - 2024` ja vaata tulemust.",
        "```\nSELECT * FROM t WHERE aasta BETWEEN 2019 - 2021;\n```",
        "```js\nconst diff = end - start; // 2020 - 2024\n```",
        "```python\nvanus = 18 - 25 aastat\n```",
        "Valem: vanus = 1990 - 2024, märk on vale.",
    ])


def percent_suffix() -> None:
    print("percent-sign-suffix: no derivational suffix on % (EKI Arvukirjutus p 30)")
    expect_found({
        "Pood pakkus 20%-list hinnaalandust ja ootab 100%-list kasvu.": [
            ("percent-sign-suffix", "20%-list", "20% / 20-protsendilist"),
            ("percent-sign-suffix", "100%-list", "100% / 100-protsendilist")],
        "Laen 5%-se intressiga.": [("percent-sign-suffix", "5%-se", "5% / 5-protsendise")],
        "Piim 3,5%-lise rasvasisaldusega.": [
            ("percent-sign-suffix", "3,5%-lise", "3,5% / 3,5-protsendilise")],
        # The suffix, not the noun after it.
        "Makstakse 10%-list lisatasu.": [
            ("percent-sign-suffix", "10%-list", "10% / 10-protsendilist")],
        # A comma glued before the number does not hide it.
        "Valikus on tooted,20%-lised soodustused.": [
            ("percent-sign-suffix", "20%-lised", "20% / 20-protsendilised")],
    })
    # Case endings on % are fine; so are the two forms EKI pairs. No form
    # of -line starts with lisa: lisa and lisatasu are nouns.
    expect_clean(["Kasv oli 10%-st 15%-ni ja langus 3%-le.", "Hind tõusis 5%.",
                  "20-protsendiline hinnaalandus ja 20% hinnaalandus.",
                  "5%-lisa töötasule makstakse ööajal.", "Ööajal makstakse 10%-lisatasu."])


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
                          "4.13. Tellija\n", "kell 10.20-12.30 ", "€14.05 ",
                          "~5 ", "`~5 ", "~5~ ", "```\n~5\n",
                          "5 - 10 päeva ", "2020 - 2024 ", "09.2016 ", "20%-line ",
                          "* ~5\n", "    ~5\n", "`` ~5 `` ", "` `` ``` ", "Kurss 11.2050 ",
                          "ülesanne 1 - 10 punkti ", "geimis 18 - 25 punktiga ",
                          "= 1990 - 2024 ", "`2020 - 2024` ")}
    # A match tried inside a digit run must not rescan the rest of it.
    texts["one 100k digit run"] = "1" * 100_000
    texts["pi to 100k digits"] = ("3," + "1415926535" * 10_000)[:100_000]
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
approximate_tilde()
month_year()
range_spacing()
percent_suffix()
issue_shape()
linear_time()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall check_numbers tests passed")
