"""Tests for the teavitama / teatama government rules of `check_object_case`.

teavitama and informeerima take the person in the partitive (keda +
millest: teavitas politseid), teatama takes the recipient in the allative
(kellele: teatas politseile). `teavitama-allative-recipient` flags the
first verb with an allative person or body, `teatama-partitive-person` the
second with a partitive personal pronoun. The sentences below are the
research set the detector was built against: every should-flag sentence is
flagged and none of the must-not ones, the second list holding the traps
correct text sets (participles and action nouns that own the allative,
genitive/partitive homographs, addresses, attributive participles). The
statute sentences quote RahaPTS.

Run via:

    uv run python tests/test_object_case.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server

TEAVITAMA = "teavitama-allative-recipient"
TEATAMA = "teatama-partitive-person"
NEW_RULES = (TEAVITAMA, TEATAMA)

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"  FAIL {label} {detail}")


def new_issues(text: str) -> list[dict]:
    return [i for i in server.check_object_case(text)["issues"] if i["rule"] in NEW_RULES]


def found(text: str) -> list[tuple[str, str]]:
    return [(i["rule"], i["word"]) for i in new_issues(text)]


def expect(cases: dict[str, list[tuple[str, str]]]) -> None:
    for text, want in cases.items():
        got = found(text)
        check(f"flags {[w for _, w in want]}: {text!r}", got == want, f"got {got}")


def expect_clean(cases: list[str]) -> None:
    for text in cases:
        got = found(text)
        check(f"clean: {text!r}", got == [], str(got))


def teavitama_flagged() -> None:
    print("teavitama-allative-recipient: flagged")
    expect({
        "Ta teavitas politseile õnnetusest.": [(TEAVITAMA, "politseile")],
        # The noun in the nominative, with genitives between it and the
        # allative. RahaPTS § 32 lg 3 writes teatamine here.
        "Kahtlasest tegevusest teavitamine Rahapesu Andmebüroole on kohustuslik.":
            [(TEAVITAMA, "Rahapesu Andmebüroole")],
        "Kohustused: andmelekkest teavitamine Andmekaitse Inspektsioonile.":
            [(TEAVITAMA, "Andmekaitse Inspektsioonile")],
        "Palun teavitage meile, kui aadress muutub.": [(TEAVITAMA, "meile")],
        "Teavitame Teile, et kauplus on pühade ajal suletud.": [(TEAVITAMA, "Teile")],
        # lapse_vanem: the head is the last part of span.root.
        "Kool teavitas lapsevanematele muudatustest tunniplaanis.":
            [(TEAVITAMA, "lapsevanematele")],
        "Muudatustest tuleb teavitada kõigile osapooltele.": [(TEAVITAMA, "kõigile osapooltele")],
        # A time measure in the partitive is no object.
        "Ettevõte teavitab klientidele hinnatõusust kuu aega ette.": [(TEAVITAMA, "klientidele")],
        "Juhtumist teavitati kohe politseile ja päästeametile.": [(TEAVITAMA, "politseile")],
        "Informeerisime kõigile osalejatele ajakava muutusest.":
            [(TEAVITAMA, "kõigile osalejatele")],
        # A participle counts after olema or ei.
        "Ta on juhtunust teavitanud politseile.": [(TEAVITAMA, "politseile")],
        "Ta ei teavitanud sellest oma tööandjale.": [(TEAVITAMA, "oma tööandjale")],
        "Kõrvaltoimetest teavitage oma arstile või apteekrile.": [(TEAVITAMA, "oma arstile")],
        "Rikkumisest teavitamine Andmekaitse Inspektsioonile toimub veebivormi kaudu.":
            [(TEAVITAMA, "Andmekaitse Inspektsioonile")],
        # The ja after Maksu- is no clause boundary.
        "Sellest teavitati ka Maksu- ja Tolliametile.": [(TEAVITAMA, "Maksu- ja Tolliametile")],
        "Õigeaegne teavitamine kõigile osapooltele on hea tava.":
            [(TEAVITAMA, "kõigile osapooltele")],
        "Teavitan teile, et koosolek lükkub edasi.": [(TEAVITAMA, "teile")],
        "Teavitasime kõigile meie klientidele uutest tingimustest.":
            [(TEAVITAMA, "kõigile meie klientidele")],
        "Teavitage kohe tööandjale, kui jääte haigeks.": [(TEAVITAMA, "tööandjale")],
        "Teavitasime asjast ametlikult ka ministeeriumile.": [(TEAVITAMA, "ministeeriumile")],
        # More from the research set.
        "Palun teavitage sellest koheselt oma juhile.": [(TEAVITAMA, "oma juhile")],
        "Teavitasin juhtunust ka naabritele.": [(TEAVITAMA, "naabritele")],
        "Tööandja peab teavitama töötajatele ohtudest.": [(TEAVITAMA, "töötajatele")],
        "Teavitage meile oma soovist kirjalikult.": [(TEAVITAMA, "meile")],
        "Teavitage koheselt tööandjale, kui jääte haigeks.": [(TEAVITAMA, "tööandjale")],
        "Teavitage meile või helistage.": [(TEAVITAMA, "meile")],
        "Teavitasime juhtunust kohe kindlustusandjale.": [(TEAVITAMA, "kindlustusandjale")],
        "Palun teavitada meile hiljemalt reedeks.": [(TEAVITAMA, "meile")],
        # The phrase runs to its allative head past a genitive noun.
        "Teavitasime uutele lepingu klientidele hinnast.":
            [(TEAVITAMA, "uutele lepingu klientidele")],
        # A determiner before a recipient noun, and pool as a party.
        "Teavitame igale kliendile eraldi.": [(TEAVITAMA, "igale kliendile")],
        "Teavitame teisele poolele kirjalikult.": [(TEAVITAMA, "teisele poolele")],
        # A translative of time and a time adverb are no experiencers.
        "Palun teavitage meile reedeks.": [(TEAVITAMA, "meile")],
        "Teavitame muudatustest kõigile korraga.": [(TEAVITAMA, "kõigile")],
        # A hard-wrapped line is no heading.
        "Kahtlasest tegevusest teavitamine\nRahapesu Andmebüroole on kohustuslik.":
            [(TEAVITAMA, "Rahapesu Andmebüroole")],
        "Ta teavitas\npolitseile õnnetusest.": [(TEAVITAMA, "politseile")],
        # These compounds name a norm or a hazard, not a person.
        "Teavitame klientidele ajakohasest teabest.": [(TEAVITAMA, "klientidele")],
        "Teavitame elanikele tuleohtlikest ainetest.": [(TEAVITAMA, "elanikele")],
        # Only a bare amet before kandideerimine or asumine is a post.
        "Ta teavitas ametile kolimisest.": [(TEAVITAMA, "ametile")],
        "Ta teavitas Maksuametile kandideerimisest.": [(TEAVITAMA, "Maksuametile")],
        "Ministeerium teavitas kandidaatidele kandideerimise tingimustest.":
            [(TEAVITAMA, "kandidaatidele")],
    })


def teavitama_clean() -> None:
    print("teavitama-allative-recipient: not flagged")
    expect_clean([
        "Ta teavitas politseid õnnetusest.",
        "Kahtlasest tegevusest teatamine Rahapesu Andmebüroole on kohustuslik.",
        # The participle after the allative owns it (RahaPTS § 93, § 51).
        "Ebaseaduslik teavitamine Rahapesu Andmebüroole edastatud andmetest on keelatud.",
        "Isikut on keelatud teavitada tema kohta Rahapesu Andmebüroole esitatud teatest.",
        "Kohustatud isik võib teavitada isikut talle seatud piirangust.",
        "Audiitor on kohustatud teavitama Finantsinspektsiooni talle tööülesannete käigus "
        "teatavaks saanud asjaoludest.",
        # Komisjoni may be a partitive out of context; andmise owns ettevõtjale.
        "Amet teavitab Euroopa Komisjoni ettevõtjale tegevusloa andmise otsusest.",
        "Teavitame klienti e-posti aadressile saadetud kirjaga.",
        # An address is no recipient.
        "Teavitame teid e-posti aadressile.",
        "Pank teavitab klienti tähtajaks.",
        # Neither the genitive, the compound, teavitus nor teavitaja triggers.
        "Teavitamise kohustus laieneb ka teistele töötajatele.",
        "Teavitamiskohustus kehtib kõigile ettevõtetele.",
        "Keda teavitada ja kellele teatada, otsustab juht.",
        "Ta teavitas juhti ja saatis kirja ka kolleegidele.",
        "Teavitage meid, kui teile saabub kiri.",
        # An adjective or participle after the phrase owns it.
        "Teavitasime kõigile olulisest muudatusest.",
        "Teavitasime kõigile meie klientidele kehtivatest tingimustest.",
        "Teavitame tulemustest kõigile osalejatele mõistetavas keeles.",
        "Teavitame klientidele mõeldud uuest teenusest.",
        # Attributive participles.
        "Juhtunust teavitanud töötajale makstakse preemiat.",
        "Igale teavitatud kliendile saadetakse kinnitus.",
        "Teavitamata jäänud kliendile saadetakse meeldetuletus.",
        # A governor before the allative owns it.
        "Muudatustest teavitatakse vastavalt seadusele.",
        "Teavitame üritusest lisaks klientidele ka koostööpartnereid.",
        "Teavitame muudatuse mõjust klientidele eraldi kirjas.",
        "Teavitati koosoleku edasilükkamisest järgmisele nädalale.",
        "Ta teavitas sellest esimesena oma naabrile helistades.",
        # arsti comes out sg g in context; the out-of-context lookup finds sg p.
        "Teavitage oma arsti kõrvaltoimetest.",
        # A genitive before the noun fills its object slot.
        "Kliendi teavitamine meie spetsialistidele usaldatakse lepinguga.",
        "Lapsevanemate teavitamine koolile on oluline.",
        "Teavitus kliendile saadetakse e-postiga.",
        "Teavitajale tagatakse konfidentsiaalsus.",
        "Teavitamine on meile oluline.",
        "Teavitame SMS-iga telefoninumbrile, mille olete meile andnud.",
        "Teavitage meid sellest, kellele kaup üle anda.",
        "Tööandja on kohustatud teatama ohust kõigile töötajatele.",
        # More from the research set.
        "Rakendus teavitab kasutajat, kui talle on saabunud uus sõnum.",
        "Arst teavitab patsienti ravi riskidest ja annab talle juhised.",
        "Teavituse saatmine kliendile võtab aega paar minutit.",
        "Lisaks teavitamisele kõigile osalejatele avaldame teate kodulehel.",
        "Tööandja teavitab töötajaid ohust ja annab neile juhised.",
        "Teavitame tulemustest hiljemalt reedeks.",
        "Teavitamine toimub kõigile ühtemoodi e-posti teel.",
        "Teavitame osalejaid koosoleku edasilükkamisest järgmisele nädalale.",
        "Teavitame kliente kirjaga, mis saadetakse nende e-posti aadressile.",
        "Teavitame vastuseks Teie pöördumisele, et taotlus on rahuldatud.",
        "Teavitage kontaktisikut, kellele kiri adresseeriti.",
        "Teavitamine kõigile osalejatele sobival ajal on oluline.",
        "Ta teavitas oma ülemust ja teatas juhtunust ka politseile.",
        "Teavitame Teid, et teile on määratud uus tähtaeg.",
        "Teavitage meid ette, et saaksime teile koha broneerida.",
        "Teavitasime ka teisi osakondi ning neile saadeti kokkuvõte.",
        "Kliente teavitame ka telefonile saadetava sõnumiga.",
        "Teavitame kõiki kliente ja oleme neile tänulikud.",
        "Teavitama peab ka kliendi esindajat.",
        "Teavitame kõiki, kellele kiri saadeti.",
        "Teavitage meid hiljemalt kolm päeva enne tähtaega.",
        "Teavitamine kõigile tuntud kanalite kaudu on kiire.",
        "Teavitasime kliendile kuuluva sõiduki omanikku.",
        "Teavitame tulemustest kirjaga, mis saadetakse kõigile osalejatele.",
        "Teavitame tulemustest kõigile osalejatele saadetava kirjaga.",
        "Teavitamine meile oluliste muudatuste kohta käib e-posti teel.",
        "Teavitusi saadame kõigile klientidele.",
        "Teavitamise eest vastutab juhatus.",
        "Rakendus teavitab sind, kui sõber saadab sulle sõnumi.",
        "Teavitame kõiki asjaosalisi ja anname neile võimaluse arvamust avaldada.",
        "Teavitasime nõukogu liikmeid ning nõukogule esitati aruanne.",
        "Teavitame Teid e-kirjaga Teie poolt märgitud aadressile.",
        "Teavitame muudatustest vastavalt klientidele saadetud teatele.",
        "Teavitame uuest hinnakirjast ka teistele klientidele mõeldud uudiskirjas.",
        "Ta ei teavitanud meid, kuigi oli seda meile lubanud.",
        "Teavitav kiri saadetakse kõigile liikmetele.",
        "Kohustus teavitada lasub tööandjal, mitte töötajale.",
        "Kas teavitada ka teisi või piisab juhile teatamisest?",
        "Teavitame klienti tähtpäevast, mis on talle määratud.",
        "Teavitage politseid ja andke neile kogu teave.",
        # The head is the allative noun, not a genitive before it: an
        # address is still no recipient.
        "Teavitame tulemustest järgmisele meie aadressile.",
        "Teavitas uutele ettevõtte aadressidele.",
        # A determiner does not make its noun a recipient: the allative is
        # the goal of the action noun before it.
        "Teavitame kontori kolimisest teisele korrusele.",
        "Teavitasime koosoleku üleviimisest teisele kuupäevale.",
        "Teavitame väljamakse tegemisest teisele kontole.",
        "Teavitame garantii pikendamisest kõigile kodumasinatele.",
        "Teavitame kampaania laienemisest kõigile kauplustele.",
        "Teavitame turvaparanduse paigaldamisest kõigile serveritele.",
        "Teavitame soodustuse kohaldamisest kõikidele tellimustele.",
        "Teavitame hinnamuutusest igale tootele eraldi.",
        # The experiencer of an adverb or a translative noun.
        "Ministeerium teavitas sellest meile teadaolevalt alles eile.",
        "Juhtunust teavitati kõigile üllatuseks alles nädal hiljem.",
        "Teavitame muudatustest kõigile arusaadavalt ja lühidalt.",
        "Ettevõte teavitas sellest kõigile nähtavalt oma kodulehel.",
        "Sellest teavitati meile kõigile rõõmuks juba hommikul.",
        "Juhatus teavitas oma otsusest kõigile ootamatult juba esmaspäeval.",
        "Juhtumist teavitati teistele hoiatuseks ka ettevõtte sisevõrgus.",
        "Teavitame tähtaja muutumisest Teile teadmiseks juba praegu.",
        # A heading line before a sentence of its own.
        "Teavitamine\nKlientidele saadetakse kiri e-postiga.",
        "Kokkuvõte\nTeavitamine\nKlientidele helistatakse järgmisel päeval.",
        "1. Teavitamine\nKlientidele saadetakse kiri.",
        "Teavitamine\r\nKlientidele meeldib uus teenus.",
        "Õigeaegne teavitamine\nKlientidele saadetakse kiri e-postiga.",
        # A compound of a listed governor governs like its last part, and
        # these adjectives take an allative of their own.
        "Amet teavitab lisatoetusest lasterikastele peredele.",
        "Teavitame maksusoodustusest peredele.",
        "Teavitame klientidele üliolulistest muudatustest.",
        "Teavitame töötajatele eluohtlikest tööoludest.",
        "Kliendid on teavitatud kõigile ühtsetest tingimustest.",
        "Terviseamet teavitab inimestele mürgistest seentest.",
        "Teavitame ratastoolikasutajatele ligipääsmatutest hoonetest.",
        # amet as a post: kandideerima ametile, asuma ametile.
        "Ministeerium teavitas kantsleri ametile kandideerimise tingimustest.",
        "Ta teavitas uuele ametile asumisest juba varakult.",
    ])


def teatama() -> None:
    print("teatama-partitive-person")
    expect({
        "Teatame Teid, et kauplus on suletud.": [(TEATAMA, "Teid")],
        "Teatame teid muudatustest hinnakirjas.": [(TEATAMA, "teid")],
        # No active participle governs the pronoun: a vocative between
        # commas, a relative clause, a passive participle, or a participle
        # that describes something else.
        "Teatame teid, kallid kliendid, muudatustest.": [(TEATAMA, "teid")],
        "Teatame Teid ohtudest, mis teid ümbritsevad.": [(TEATAMA, "Teid")],
        "Teatame teid muudatustest ja lisatud tingimustest.": [(TEATAMA, "teid")],
        "Teatame teid muudatustest kehtivas hinnakirjas.": [(TEATAMA, "teid")],
    })
    # Only the narrow form: a participle after the pronoun governs it, and
    # teatama with an allative or a content object is right.
    expect_clean([
        "Teatame teile kahetsusega, et üritus jääb ära.",
        "Teatame Teid puudutavatest muudatustest kirja teel.",
        "Teatame Teid huvitavast pakkumisest.",
        "Teatasime teda puudutavast otsusest kirjalikult.",
        "Teatame teile muudatustest.",
        "Teatame kõigile klientidele, et kontor on suletud.",
        "Teatame Teile, et Teid on valitud.",
        "Teatan teile, et teid ootab üllatus.",
        "Teatame teid huvitavatest uudistest.",
        # The participle may be tagged a noun (ümbritsev), stand after a
        # comma, a coordinated object or an adverbial elative.
        "Teatame Teid ümbritsevatest ohtudest.",
        "Teatame Teid, Teie perekonda ja lähedasi puudutavast otsusest.",
        "Teatame teid, kallid kliendid, puudutavatest muudatustest.",
        "Teatame meid südamest rõõmustanud uudisest.",
        "Teatame teid algusest peale huvitanud küsimuse lahendusest.",
        "Teatame teid kodust kontorisse viiva bussiliini muudatustest.",
    ])


def issue_shape() -> None:
    print("issue shape")
    keys = {"word", "lemma", "position", "form", "verb", "rule", "rule_estonian", "suggestion"}
    text = ("Ta teavitas politseile õnnetusest. Kahtlasest tegevusest teavitamine Rahapesu "
            "Andmebüroole on kohustuslik. Teatame Teid, et kauplus on suletud. "
            "Teavitasime kõigile meie klientidele uutest tingimustest. "
            "Informeerisime kõigile osalejatele ajakava muutusest.")
    got = new_issues(text)
    check("five issues", len(got) == 5, str(got))
    check("every issue has word, lemma, position, form, verb, rule, rule_estonian, suggestion",
          all(set(i) == keys for i in got), str(got))
    check("position points at word",
          all(text[i["position"]:i["position"] + len(i["word"])] == i["word"] for i in got),
          str(got))
    check("issues come in text order",
          [i["position"] for i in got] == sorted(i["position"] for i in got), str(got))
    rows = [(i["lemma"], i["form"], i["verb"], i["rule_estonian"], i["suggestion"]) for i in got]
    want = [
        ("politsei", "sg all", "teavitama", "teavitama: keda, mitte kellele",
         "politseid (teavitama) / teatama + politseile"),
        # The noun's object is a genitive before it.
        ("andmebüroo", "sg all", "teavitamine", "teavitama: keda, mitte kellele",
         "Rahapesu Andmebüroo teavitamine / teatamine + Rahapesu Andmebüroole"),
        ("sina", "pl p", "teatama", "teatama: kellele, mitte keda",
         "Teile (teatama) / teavitama + Teid"),
        ("klient", "pl all", "teavitama", "teavitama: keda, mitte kellele",
         "kõiki meie kliente (teavitama) / teatama + kõigile meie klientidele"),
        ("osaleja", "pl all", "informeerima", "teavitama: keda, mitte kellele",
         "kõiki osalejaid (informeerima) / teatama + kõigile osalejatele"),
    ]
    for row, w in zip(rows, want, strict=False):
        check(f"fields and suggestion for {w[4].split(' / ')[-1]!r}", row == w, str(row))
    got = new_issues("Sellest teavitati ka Maksu- ja Tolliametile.")
    check("a hyphenated coordination is rewritten whole",
          [i["suggestion"] for i in got]
          == ["Maksu- ja Tolliametit (teavitama) / teatama + Maksu- ja Tolliametile"], str(got))
    got = new_issues("Õigeaegne informeerimine kõigile osapooltele on hea tava.")
    check("informeerimine is the noun's verb, its object a genitive",
          [(i["verb"], i["suggestion"]) for i in got]
          == [("informeerimine",
               "kõigi osapoolte informeerimine / teatamine + kõigile osapooltele")], str(got))
    got = new_issues("TEAVITAS POLITSEILE.")
    check("the suggestion keeps the letter case",
          [i["suggestion"] for i in got] == ["POLITSEID (teavitama) / teatama + POLITSEILE"],
          str(got))
    # A lemma with two paradigms (kool: kooli and koola) is inflected in
    # the one the allative in the text belongs to, a compound under its
    # last part (lepingupool: poole and pooli).
    for text, want in {
        "Ministeerium teavitas koolile muudatusest.": "kooli (teavitama) / teatama + koolile",
        "Teavitamine kõigile koolidele on kohustuslik.":
            "kõigi koolide teavitamine / teatamine + kõigile koolidele",
        "Teavitame kõigile lepingupooltele.":
            "kõiki lepingupooli (teavitama) / teatama + kõigile lepingupooltele",
    }.items():
        got = new_issues(text)
        check(f"suggestion {want.split(' / ')[0]!r}", [i["suggestion"] for i in got] == [want],
              str(got))
    # seade 'device' (seadme) against seade 'setting': no seade is a
    # recipient, so the helper itself.
    got = [server._teav_synth_like("seade", "pl all", "S", w, "pl p")
           for w in ("seadmetele", "seadetele")]
    check("seadmetele gives seadmeid, seadetele seadeid", got == ["seadmeid", "seadeid"], str(got))
    # The new rules run before the negation gate and beside the old rules.
    r = server.check_object_case("Ma ei söönud leib. Ta teavitas politseile õnnetusest.")
    check("old and new rules together",
          [(i["rule"], i["word"]) for i in r["issues"]]
          == [("negation-requires-partitive", "leib"), (TEAVITAMA, "politseile")],
          str(r["issues"]))
    check("summary counts every issue", r["summary_estonian"].startswith("Leiti 2 "),
          r["summary_estonian"])


def linear_time() -> None:
    print("linear time on 100,000 characters")
    server.check_object_case("Ta teavitas politseile õnnetusest.")   # warm the models
    unit = "Ta teavitas politseile õnnetusest. Teatame Teid, et kauplus on suletud. "
    texts = {
        "many short sentences": (unit * (100_000 // len(unit) + 1))[:100_000],
        "plain prose": ("Mees ei söönud leiba ja läks koju. " * 3000)[:100_000],
        "one clause of triggers": ("teavitas kõigile " * 7000)[:100_000],
        "one long allative run": ("teavitas " + "kõigile " * 12_500)[:100_000],
        "participle chain": ("on " + "teavitatud " * 9100)[:100_000],
        "heading lines": ("Teavitamine\nKlientidele saadetakse kiri.\n" * 2500)[:100_000],
        "teatama before commas": ("Teatame teid, " * 7200)[:100_000],
        "one teatama clause": ("Teatame teid " + "kallid kliendid, " * 6000)[:100_000],
        "experiencer runs": ("teavitas meile kõigile rõõmuks " * 3300)[:100_000],
    }
    for label, text in texts.items():
        t = time.perf_counter()
        tagged = server._Text()(text)
        tagged.tag_layer(["sentences", "morph_analysis"])
        tagging = time.perf_counter() - t
        t = time.perf_counter()
        server.check_object_case(text)
        dt = time.perf_counter() - t
        # EstNLTK's own tagging is most of it. Filtering every word per
        # sentence took 18 to 25 s here where tagging took 4 to 6 s.
        check(f"{label}: {dt:.2f} s, tagging {tagging:.2f} s", dt < 2 * tagging + 3,
              f"{dt:.2f} s against {tagging:.2f} s")


def lookups() -> None:
    print("out-of-context lookups: cached and capped")
    roots = ["maja", "kooli", "aia", "puu", "kivi", "vee", "tee", "linna", "metsa", "auto",
             "raamatu", "laua", "töö", "ilma", "maa", "kala", "lille", "saare", "ase", "osa"]
    # Each sentence puts a new genitive between teavitama and a recipient,
    # the one place a word is looked up out of context.
    words = ("".join(roots[(n * 7919 // 20 ** k) % 20] for k in range(6)) + "omaniku"
             for n in range(4000))
    text = "".join(f"Ta teavitas {w} sõbrale. " for w in words)[:100_000]
    real, calls = server._vabamorf, []

    class Counting:
        def analyze(self, **kwargs):
            calls.append(kwargs["words"])
            return real().analyze(**kwargs)

        def __getattr__(self, name):
            return getattr(real(), name)

    server._teav_may_be_partitive.cache_clear()
    server._vabamorf = Counting
    try:
        t = time.perf_counter()
        first = server.check_object_case(text)["issues"]
        dt = time.perf_counter() - t
        n_first = len(calls)
        server.check_object_case(text)
    finally:
        server._vabamorf = real
    check(f"{n_first} lookups for {text.count('teavitas')} sentences, {dt:.2f} s",
          0 < n_first <= server._TEAV_LOOKUPS, str(n_first))
    # A word repeats now and then, and its second sentence is flagged from
    # the call's own lookups.
    check(f"past the budget a word counts as a possible object: {len(first)} flagged",
          0 < len(first) < text.count("teavitas") // 2, str(len(first)))
    check("a repeated text is answered from the cache", len(calls) == n_first,
          str(len(calls) - n_first))


teavitama_flagged()
teavitama_clean()
teatama()
issue_shape()
linear_time()
lookups()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall check_object_case government tests passed")
