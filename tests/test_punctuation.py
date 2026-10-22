"""Tests for `check_punctuation`: two-part connectives and `nagu`.

The EKI rules these pin (EKI teatmik, "Koma": ühendsidendid, kui- ja
nagu-tarind, koma nihkumine; õigekirja põhireeglid, reegel 44):

1. A TWO-PART CONNECTIVE TAKES ITS COMMA BEFORE THE WHOLE OF IT (Sadas
   vihma, nii et jäime koju; Ta lahkus, ilma et oleks hüvasti jätnud), or,
   for sellepärast et, selleks et, nii et and the like, between the parts
   when the first part belongs to the main clause (Tulin selleks, et
   aidata). ilma et, olgugi et and the like never take one between. The
   tool used to flag `et` in every one of these, and its suggestion `, et`
   turned a correct `ilma et` into the wrong `ilma, et`.

2. nagu TAKES A COMMA ONLY WHEN IT OPENS A CLAUSE WITH A FINITE VERB
   (Vaatas mind, nagu oleksin võõras). A verbless comparison takes none
   (Vaatas mind nagu võõrast; tugev nagu karu), and the tool flagged every
   one of those.

3. A CONJUNCTION BEFORE A SUBORDINATOR TAKES THE COMMA ITSELF: `..., et
   tuleb ja et toob kooki`, never `ja, et`.

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


def one(text: str, word: str, suggestion: str, at: str | None = None,
        rule: str = "comma-before-clause-conjunction") -> None:
    """Exactly one issue, on `word`, starting where `at` (default `word`)
    first occurs in the text."""
    got = issues(text)
    want_pos = text.index(at if at is not None else word)
    check(f"one flag on {word!r} -> {suggestion!r}: {text}",
          len(got) == 1
          and got[0]["word"] == word
          and got[0]["suggestion"] == suggestion
          and got[0]["position"] == want_pos
          and got[0]["rule"] == rule
          and bool(got[0].get("rule_estonian")),
          str(got))


print("a comma before the whole connective is right")
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
    "Võtan selle, eeldusel et hind on õige.",
    "Aadel vandus truudust, tingimusel et privileegid säilivad.",
    "Sõime edasi, olgugi et kõht oli juba täis.",
    "Kõik oli hästi, ainult et raha oli vähe.",
    "Söö, mida tahad, peaasi et kõht saab täis.",
    "Ta jõudis koju, vaevalt et keegi märkas.",
):
    clean(text)

print("a comma between the parts is right where the first part is the main clause's")
for text in (
    "Tulin selleks, et aidata.",
    "Tegin nii, nagu kokku lepiti.",
    "Tegin nii, et kõik said aru.",
    "Lõke ei süttinud sellepärast, et puud olid märjad.",
    "Ta tuli tööle hoolimata sellest, et oli haige.",
    "Ma tahan ainult, et sa oleksid õnnelik.",
    "Mul on ükskõik, kuhu sa lähed.",
    # ilma belongs to `jäi ilma` (went without), or is the noun ilm.
    "Ta jäi ilma, et teised saaksid.",
    "Ta ootas ilusat ilma, et minna randa.",
):
    clean(text)

print("a connective that opens the sentence needs no comma")
for text in (
    "Olgugi et kõht oli juba täis, sõime edasi.",
    "Ilma et keegi teaks, lahkus ta.",
    "Selle asemel et kurta, tegutse.",
    "Selleks et aidata, tulin varem.",
    "Nii et me jäime koju.",
    "Vaevalt et ta tuleb.",
    "Ükskõik kuhu sa lähed, ma tulen kaasa.",
):
    clean(text)

print("ükskõik kuhu (= kuhu tahes) opens no clause")
clean("Võid minna ükskõik kuhu.")

print("a conjunction before a subordinator takes the comma itself")
clean("Ta ütles, et tuleb ja et toob kooki.")
clean("Ta tuli, kuid kuna oli hilja, läks ta varsti ära.")
one("Ta ei tulnud sest et oli haige.", "sest", ", sest")

print("no comma anywhere: one flag, before the whole connective")
one("Sadas vihma nii et jäime koju.", "nii et", ", nii et")
one("Tulin selleks et aidata.", "selleks et", ", selleks et")
one("Ta lahkus ilma et oleks hüvasti jätnud.", "ilma et", ", ilma et")
one("Lõke ei süttinud sellepärast et puud olid märjad.",
    "sellepärast et", ", sellepärast et")
one("Ta jäi koju seetõttu et oli haige.", "seetõttu et", ", seetõttu et")
one("Ta tegutses selle asemel et kurta.", "selle asemel et", ", selle asemel et")
one("Ta tuli tööle hoolimata sellest et oli haige.",
    "hoolimata sellest et", ", hoolimata sellest et")
one("Ta tuli vaatamata sellele et oli väsinud.",
    "vaatamata sellele et", ", vaatamata sellele et")
one("Sõime edasi olgugi et kõht oli täis.", "olgugi et", ", olgugi et")
one("Kõik oli hästi ainult et raha oli vähe.", "ainult et", ", ainult et")
one("Ta tuli koju nii nagu ta alati tuleb.", "nii nagu", ", nii nagu")
one("Ma jään siia ilma et keegi teaks.", "ilma et", ", ilma et")

print("no comma anywhere, first part the main clause's: the comma goes before et")
# nii or ainult right after a finite verb is that verb's (EKI: the manner
# nii et takes the comma between its parts).
one("Tegin nii et kõik said aru.", "et", ", et")
one("Tegin nii nagu kokku lepiti.", "nagu", ", nagu")
one("Tee just nii et keegi ei näe.", "et", ", et")
one("Ma tahan ainult et sa oleksid õnnelik.", "et", ", et")
# A focus particle makes the first part a stressed main-clause word.
one("Tulin just selleks et aidata.", "et", ", et")
# ilma as the main clause's adverb or the noun ilm: the old answer stands.
one("Ta jäi rahast ilma et teised saaksid.", "et", ", et")
one("Ta ootas ilusat ilma et minna randa.", "et", ", et")
one("Mul on ükskõik kuhu sa lähed.", "kuhu", ", kuhu")

print("a comma inside ilma et or olgugi et is wrong")
# The old tool's own suggestion produced these.
one("Ta lahkus ilma, et oleks hüvasti jätnud.", "ilma, et", ", ilma et",
    rule="no-comma-inside-conjunction")
one("Ilma, et keegi teaks, lahkus ta.", "Ilma, et", "Ilma et",
    rule="no-comma-inside-conjunction")
one("Sõime edasi olgugi, et kõht oli täis.", "olgugi, et", ", olgugi et",
    rule="no-comma-inside-conjunction")

print("a verbless nagu comparison takes no comma")
for text in (
    "Ta on tugev nagu karu.",
    "Ta jooksis nagu tuul.",
    "Ta on valge nagu lumi.",
    "Vaatas mind nagu võõrast.",
    "Ta käitus nagu laps.",
    "Ta on samasugune nagu ema.",
    # tuli is also the noun "fire"; the sentence analysis reads it as a verb.
    "Ta oli punane nagu tuli.",
    # The finite verb after the comparison is the main clause's (EKI).
    "Kassid nagu kõik koduloomad vajavad hoolitsust.",
    "Sina nagu minagi tahame puhata.",
    # A conjunction or a relative word ends the comparison.
    "Ta jooksis nagu tuul ja hüppas üle aia.",
    "Ta on tugev nagu karu kes elab metsas.",
    "Ta jooksis nagu ei keegi teine.",
    # nagu the particle ("kind of").
    "Ma nagu ei tea.",
    "Ta on tugev nii nagu karu.",
):
    clean(text)

print("a nagu clause with a finite verb takes the comma")
one("Tee nagu tahad.", "nagu", ", nagu")
one("Ta rääkis nagu oleks ta seal olnud.", "nagu", ", nagu")
one("Vaatas mind nagu oleksin võõras.", "nagu", ", nagu")
one("Ma tegin nagu sina tegid.", "nagu", ", nagu")
one("Ta käitus nagu ta ei teadnud midagi.", "nagu", ", nagu")
one("Ta käitus nagu poleks midagi juhtunud.", "nagu", ", nagu")
one("Tundub nagu keegi oleks siin.", "nagu", ", nagu")
one("Ta vastas nagu kästi.", "nagu", ", nagu")

print("the single conjunctions still fire")
one("Ma tean et see on hea.", "et", ", et")
one("Ta ei tulnud sest oli haige.", "sest", ", sest")
one("Ta tuli kuid lahkus kohe.", "kuid", ", kuid")
one("Ma ei käinud mitte Prahas vaid Viinis.", "vaid", ", vaid")
one("Ta jäi koju kuigi ilm oli ilus.", "kuigi", ", kuigi")
one("Ta ei tulnud kuna oli haige.", "kuna", ", kuna")
one("Ta oli haige mistõttu ta ei tulnud.", "mistõttu", ", mistõttu")
one("Ta oli haige millepärast ta ei tulnud.", "millepärast", ", millepärast")
one("Ma ei tea kuhu ta läks.", "kuhu", ", kuhu")
one("Ta oli nii väsinud et jäi magama.", "et", ", et")

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
