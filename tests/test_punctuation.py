"""Tests for `check_punctuation`: two-part connectives and `nagu`.

0.8.0 flagged every et, kuna, sest, kuigi, kuid, vaid, nagu, mistõttu,
millepärast and kuhu that no comma, semicolon, colon, dash, opening
bracket or sentence end preceded. These tests pin the two places that
changed, against the EKI rules (EKI teatmik, "Koma": ühendsidendid,
kui- ja nagu-tarind), and pin 0.8.0's answer everywhere else:

1. A TWO-PART CONNECTIVE MAY TAKE ITS COMMA BEFORE THE WHOLE OF IT (Sadas
   vihma, nii et jäime koju; Tulin, selleks et aidata). One of those
   marks, an opening quotation mark, or the sentence start before
   the first part (nii, ilma, olgugi, selleks, sellepärast, seepärast,
   seetõttu, vaevalt, peaasi, ainult, mitte, selle asemel, hoolimata
   sellest, olenemata sellest, vaatamata sellele; nii before nagu) sets
   the connective off, and nothing is flagged. With no comma anywhere,
   ilma et and olgugi et, which EKI never splits, are flagged at the first
   part (`, ilma et`); the others keep 0.8.0's `, et`, as the comma goes
   between the parts when the first part is the main clause's (Tegin nii,
   et kõik said aru).

2. nagu TAKES A COMMA WHEN IT OPENS A CLAUSE WITH A FINITE VERB (Vaatas
   mind, nagu oleksin võõras), none in a verbless comparison (tugev nagu
   karu). nagu is flagged only when a word after it, before the next
   clause punctuation, coordinator or subordinator, has a finite verb
   reading in any of its analyses, so a homograph such as sõnas or tuli
   counts.

Every flag's suggestion, applied, must give text the tool accepts (one
tokenizer exception is marked).

Run via:

    uv run python tests/test_punctuation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"  FAIL {label} {detail}")


def issues(text: str) -> list[dict]:
    return server.check_punctuation(text)["issues"]


def clean(text: str) -> None:
    got = issues(text)
    check(f"no flag: {text}", got == [], str(got))


def one(text: str, word: str, at: str | None = None, refix: bool = True) -> None:
    """Exactly one issue, on `word`, starting where `at` (default `word`)
    first occurs in the text, suggesting `, word`, and, unless `refix` is
    off, the text with the suggestion applied passes."""
    got = issues(text)
    want_pos = text.index(at if at is not None else word)
    check(f"one flag on {word!r}: {text}",
          len(got) == 1
          and got[0]["word"] == word
          and got[0]["suggestion"] == f", {word}"
          and got[0]["position"] == want_pos
          and got[0]["rule"] == "comma-before-clause-conjunction"
          and got[0]["rule_estonian"] == "koma alistava sidesõna ees"
          and set(got[0]) == {"word", "position", "rule", "rule_estonian", "suggestion"},
          str(got))
    if refix and len(got) == 1:
        pos, length = got[0]["position"], len(got[0]["word"])
        fixed = text[:pos].rstrip() + got[0]["suggestion"] + text[pos + length:]
        again = issues(fixed)
        check(f"  its fix passes: {fixed}", again == [], str(again))


print("a comma before the whole connective passes")
for text in (
    "Sadas vihma, nii et jäime koju.",
    "Tulin, selleks et aidata.",
    "Ta lahkus, ilma et oleks hüvasti jätnud.",
    "Kõik läks hästi, nii nagu me lootsime.",
    "Lõke ei süttinud, sellepärast et puud olid märjad.",
    "Ta jäi koju, seepärast et oli haige.",
    "Ta jäi koju, seetõttu et oli haige.",
    "Ta tegutses, selle asemel et kurta.",
    "Ta tuli tööle, hoolimata sellest et oli haige.",
    "Me jätkame, olenemata sellest et ilm on halb.",
    "Ta tuli, vaatamata sellele et oli väsinud.",
    "Sõime edasi, olgugi et kõht oli juba täis.",
    "Kõik oli hästi, ainult et raha oli vähe.",
    "Söö, mida tahad, peaasi et kõht saab täis.",
    "Ta jõudis koju, vaevalt et keegi märkas.",
    "Ma tulin, mitte et sind aidata.",
    "Mul on kõik olemas; ainult et raha on vähe.",
    "Ta tuli (selleks et aidata) varem.",
    "Sadas vihma \u2013 nii et jäime koju.",
    # The comma inside the closing quotation mark sets it off too.
    "Ta ütles „jah,“ nii et läksime koju.",
):
    clean(text)

print("a connective that opens a sentence or a quotation needs no comma")
for text in (
    "Olgugi et kõht oli juba täis, sõime edasi.",
    "Ilma et keegi teaks, lahkus ta.",
    "ILMA ET KEEGI TEAKS, LAHKUS TA.",
    "Selle asemel et kurta, tegutse.",
    "Selleks et aidata, tulin varem.",
    "Nii et me jäime koju.",
    "Vaevalt et ta tuleb.",
    "Nii nagu ma ütlesin, nii see läks.",
    "Ta ütles: „Nii et homme ei tule keegi.“",
    'Ta ütles: "Nii et homme ei tule keegi."',
    "«Nii et me jääme koju,» ütles ta.",
    "„Jah.“ Nii et läksime koju.",
    "- Nii et kõik on korras.",
):
    clean(text)

print("ilma et and olgugi et: the comma goes before the first part")
one("Ta lahkus ilma et oleks hüvasti jätnud.", "ilma et")
one("Ma jään siia ilma et keegi teaks.", "ilma et")
one("Sõime edasi olgugi et kõht oli täis.", "olgugi et")
one("Ta lahkus kodust ilma et keegi märkaks.", "ilma et")
one("Ta ostis uue ilma et oleks vana müünud.", "ilma et")
one("TA LAHKUS ILMA ET KEEGI MÄRKAKS.", "ILMA ET")
# A particle before the connective does not split it either.
one("Ta lahkus lihtsalt ilma et oleks hüvasti jätnud.", "ilma et")
one("Ta tuli ikka olgugi et oli haige.", "olgugi et")
# The word is the text as written, so applying the suggestion is exact.
one("Ta lahkus ilma  et keegi märkaks.", "ilma  et")

print("the other connectives with no comma: 0.8.0's `, et`")
# EKI: the manner nii et takes the comma between its parts (Tehke see töö
# ära nii, et keegi ei näe); the tool cannot tell manner from result.
one("Tehke see töö ära nii et keegi ei näe.", "et")
one("Tegin nii et kõik said aru.", "et")
one("Sadas vihma nii et jäime koju.", "et")
one("Tulin selleks et aidata.", "et")
one("Ta jäi koju seetõttu et oli haige.", "et", at="et oli")
one("Ta tegutses selle asemel et kurta.", "et")
one("Ta tuli tööle hoolimata sellest et oli haige.", "et")
one("Ma tahan ainult et sa oleksid õnnelik.", "et")
# peaasi as the predicative, vaevalt as the verb's adverb (EKI: ..., et).
one("Minu jaoks on peaasi et lapsed on terved.", "et")
one("Ta märkas vaevalt et keegi oli tuppa tulnud.", "et")
# A closing quotation mark glued to the word before it sets nothing off.
one("Ta ütles „jah“ nii et läksime koju.", "et")
one('Ta ütles "jah" nii et läksime koju.', "et")
one("Tee nii nagu tahad.", "nagu")

print("an existing comma is never flagged, as in 0.8.0")
for text in (
    "Ta lahkus ilma, et oleks hüvasti jätnud.",
    "Tegin nii, et kõik said aru.",
    "Tulin selleks, et aidata.",
    # ilma here is the noun ilm, and the comma before et is right.
    "Lootsime sooja ilma, et saaks ujuma minna.",
    "Ta rändas aastaid mööda ilma, et leida oma juuri.",
):
    clean(text)

print("a verbless nagu comparison takes no comma")
for text in (
    "Ta on tugev nagu karu.",
    "Ta jooksis nagu tuul.",
    "Ta on valge nagu lumi.",
    "Vaatas mind nagu võõrast.",
    "Ta käitus nagu laps.",
    "Ta on samasugune nagu ema.",
    "Ta on tugev nii nagu karu.",
    "Ta oli rahulik nagu tavaliselt.",
    "Ta käitub nagu kõik teised.",
    # The comparison ends at a coordinator, a subordinator or a comma.
    "Ta jooksis nagu tuul ja hüppas üle aia.",
    "Ta on tugev nagu karu, aga mitte nii tark.",
    # A participle is no predicate.
    "Ta tegi nagu kokku lepitud.",
):
    clean(text)

print("a nagu clause with a finite verb takes the comma")
one("Kõik läks nagu võis arvata.", "nagu")
one("Tee nagu tahad.", "nagu")
one("„Tee nagu tahad,“ ütles ema.", "nagu")
one("Ta rääkis nagu oleks ta seal olnud.", "nagu")
one("Vaatas mind nagu oleksin võõras.", "nagu")
one("Ta käitus nagu ta ei teadnud midagi.", "nagu")
one("Ta käitus nagu poleks midagi juhtunud.", "nagu")
one("Ta vastas nagu kästi.", "nagu")
one("Tee nii nagu ema palus.", "nagu")
one("Tulemused olid paremad kui eelmisel aastal nagu juhataja märkis.", "nagu")
one("Hinnad tõusid (eriti toidukaupadel) nagu analüütikud olid ennustanud.", "nagu")
# The tokenizer glues a comma to the euro sign (`€,`), so the fixed text
# is flagged again, as in 0.8.0.
one("Pilet maksab 15 € nagu korraldajad teatasid.", "nagu", refix=False)
one("Ta ostis leiba ja piima nagu ema oli palunud.", "nagu")
one("Leping lõpeb nagu TLS § 97 ette näeb.", "nagu")
one("Ta ütles „jah“ nagu oleks see iseenesestmõistetav.", "nagu")
one("Lisa soola nagu retseptis on kirjas.", "nagu")
one("- Lisa munad ükshaaval nagu retseptis on kirjas", "nagu")
one("ok\ntee nagu tahad", "nagu")
one("Eesti majandus nagu analüütikud ennustasid kasvas kaks protsenti.", "nagu")
one("Hind tõusis nagu nii analüütikud kui ka ettevõtjad olid oodanud.", "nagu")

print("a verb that is also a noun counts: every reading is read")
one("Olukord on keeruline nagu peaminister sõnas.", "nagu")
one("Hinnad tõusevad nagu juhatuse esimees lisas.", "nagu")
one("Ta oli süütu nagu hiljem selgus.", "nagu")
one("Raport valmis nagu tellija soovis.", "nagu")
one("Töötus kasvas 7,2 protsendini nagu Eesti Pank prognoosis.", "nagu")
one("HIND LANGES NAGU VÕIS ARVATA.", "NAGU")

print("documented limits")
# The main clause's verb after a verbless comparison (EKI: no comma).
one("Kassid nagu kõik koduloomad vajavad hoolitsust.", "nagu")
# A noun that is also a verb form (tuli = came, jää = stay).
one("Ta oli punane nagu tuli.", "nagu")
# ilma as the noun ilm before an et clause, with no comma: the suggestion
# should be `, et`.
one("Ta ootas ilusat ilma et minna randa.", "ilma et")

print("the single subordinators keep 0.8.0's answer")
one("Ma tean et see on hea.", "et")
one("Ta ei tulnud sest oli haige.", "sest")
one("Ta tuli kuid lahkus kohe.", "kuid")
one("Ma ei käinud mitte Prahas vaid Viinis.", "vaid")
one("Ta jäi koju kuigi ilm oli ilus.", "kuigi")
one("Ta ei tulnud kuna oli haige.", "kuna")
one("Ta oli haige mistõttu ta ei tulnud.", "mistõttu")
one("Ta oli haige millepärast ta ei tulnud.", "millepärast")
one("Ma ei tea kuhu ta läks.", "kuhu")
one("Ta oli nii väsinud et jäi magama.", "et")
one("Mulle on täiesti ükskõik kuhu me sõidame.", "kuhu")
one("Sulata või et see seguneks paremini.", "et")
one("Tahtsin helistada aga et oli hilja kirjutasin kirja.", "et")
# After a closing quotation mark the comma is still missing.
one("Ta vastas „ei“ sest tal polnud aega.", "sest")
one("Minister nimetas eelnõu „ajalooliseks“ sest see lahendab probleemi.", "sest")
one('Lepingus nimetatakse tellijat "Tellija" kuna see lihtsustab teksti.', "kuna")
one("Firma nimetas uue toote «Vikerkaar» kuigi turundusosakond oli vastu.", "kuigi")
two = issues("Tööandja peab tagama et töötaja saab puhkust nagu töölepingu seaduse § 55 sätestab.")
check("et and nagu in one sentence", [i["word"] for i in two] == ["et", "nagu"], str(two))
for text in (
    "Ma arvan, et kõik on hästi.",
    "Ta ei tulnud, sest oli haige.",
    "Ta küsis: kuhu sa lähed?",
):
    clean(text)

print("the description no longer documents the fixed misfires")
doc = server.check_punctuation.__doc__ or ""
check("no pair caveat", "comma goes before the pair" not in doc, doc)
check("no verbless-nagu caveat", "tugev nagu karu" not in doc, doc)
check("no em or en dash", "\u2014" not in doc and "\u2013" not in doc, doc)

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall punctuation tests passed")
