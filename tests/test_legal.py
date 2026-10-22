"""Tests for the legal-Estonian tools (check_legalese, check_defined_terms).

Both are pure (Vabamorf morphology + regex, no fastText/WordNet), so they run
locally without the model artifacts. The check_compound_familiarity legal
de-noise assertion lives in test_smoke.py (it needs the fastText model, which
only CI has).

Run via:

    uv run python tests/test_legal.py
"""
from __future__ import annotations

import re
import sys
import time
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


def legalese_tests() -> None:
    print("check_legalese")
    para = ("Käesolevas seaduses sätestatut kohaldatakse võlasuhetele. "
            "Juhul kui võlgnik ei täida kohustust, tekib võlausaldaja ees "
            "vastutus ning õigus nõuda kahjuhüvitist.")
    r = server.check_legalese(para)
    rules = {i["rule"] for i in r["issues"]}
    check("flags 'käesolev' archaic filler", "archaic-filler" in rules, str(r["issues"]))
    check("flags 'juhul kui' phrase", "legalese-phrase" in rules, str(r["issues"]))
    # käesolev suggestion is the plain 'see'
    kaes = next((i for i in r["issues"] if i["rule"] == "archaic-filler"), {})
    check("käesolev → see", kaes.get("suggestion") == "see", str(kaes))
    # terms of art are surfaced and NOT flagged as filler
    lemmas = {t["lemma"] for t in r["terms_of_art"]}
    check("protects legal term võlgnik", "võlgnik" in lemmas, str(lemmas))
    check("protects several terms of art", len(r["terms_of_art"]) >= 4, str(lemmas))
    check("no legal term is flagged as filler",
          not any(server._is_legal_term(i.get("word", "")) for i in r["issues"] if "word" in i),
          str(r["issues"]))
    # The caller's own text and a fixed note are not sent back; the
    # terms of art keep their first-occurrence anchor.
    check("no input echo or static note", "text" not in r and "note" not in r, str(sorted(r)))
    check("result keys", set(r) == {"issues", "terms_of_art", "summary_estonian"}, str(sorted(r)))
    check("terms_of_art keep their position",
          all(isinstance(t.get("position"), int) for t in r["terms_of_art"]), str(r["terms_of_art"]))

    # Plain modern Estonian: no archaic-filler flags, no terms of art.
    clean = server.check_legalese("See on lühike ja selge lause.")
    check("plain text → no archaic-filler",
          not any(i["rule"] == "archaic-filler" for i in clean["issues"]), str(clean["issues"]))

    # Over-long sentence → complex-sentence flag.
    long_s = ("Pool kohustub, arvestades kõiki asjaolusid, tingimusi, tähtaegu "
              "ja erandeid, mis tulenevad seadusest, lepingust, tavast ning "
              "kohtupraktikast, täitma oma kohustused nõuetekohaselt, õigel ajal "
              "ja täies ulatuses ilma põhjendamatu viivituseta.")
    ls = server.check_legalese(long_s)
    check("flags over-long sentence", any(i["rule"] == "complex-sentence" for i in ls["issues"]),
          str([i["rule"] for i in ls["issues"]]))
    cs = next((i for i in ls["issues"] if i["rule"] == "complex-sentence"), {})
    check("complex-sentence explanation is the per-sentence count only",
          re.fullmatch(r"Lause on \d+ sõna ja \d+ koma\.", cs.get("explanation", "")) is not None,
          str(cs))
    check("complex-sentence keeps its suggestion",
          cs.get("suggestion") == "jaga lause lühemateks osadeks", str(cs))
    check("complex-sentence keeps the issue keys",
          set(cs) == {"phrase", "position", "rule", "rule_estonian", "explanation", "suggestion"},
          str(sorted(cs)))


def defined_terms_tests() -> None:
    print("check_defined_terms")
    contract = ('Käesoleva lepingu (edaspidi «Leping») pooled on AS Müük '
                '(edaspidi «Müüja») ja OÜ Ostja (edaspidi «Ostja»). Müüja annab '
                'kauba üle. Ostja tasub hinna vastavalt Lepingu punkt 3 ja § 5 lg 2. '
                'Pooled (edaspidi «Pooled») kinnitavad, et Leping jõustub.')
    d = server.check_defined_terms(contract)
    defined = {t["term"] for t in d["defined_terms"]}
    check("extracts «Leping»", "Leping" in defined, str(defined))
    check("extracts «Müüja» and «Ostja»", {"Müüja", "Ostja"} <= defined, str(defined))
    xrefs = {x["reference"] for x in d["cross_references"]}
    check("finds 'punkt 3' cross-ref", any("punkt 3" in x for x in xrefs), str(xrefs))
    check("finds '§ 5' cross-ref", any(x.startswith("§") for x in xrefs), str(xrefs))
    # every defined term here is used again → no unused issues
    check("used terms → no defined-but-unused",
          not any(i["rule"] == "defined-but-unused" for i in d["issues"]), str(d["issues"]))
    # No preview of the caller's document and no fixed note.
    check("no text preview or note", "text" not in d and "note" not in d, str(sorted(d)))
    check("result keys",
          set(d) == {"defined_terms", "cross_references", "issues", "summary_estonian"},
          str(sorted(d)))

    # defined-but-unused detection
    unused = server.check_defined_terms("Käesolev kokkulepe (edaspidi «Kokkulepe») jõustub täna.")
    check("flags defined-but-unused",
          any(i["rule"] == "defined-but-unused" for i in unused["issues"]), str(unused["issues"]))
    un = next((i for i in unused["issues"] if i["rule"] == "defined-but-unused"), {})
    check("defined-but-unused keeps its term-specific explanation",
          "«Kokkulepe»" in un.get("explanation", ""), str(un))

    # duplicate definition
    dup = server.check_defined_terms(
        "Pool (edaspidi «Müüja») ja teine (edaspidi «Müüja»). Müüja tegutseb.")
    check("flags duplicate-definition",
          any(i["rule"] == "duplicate-definition" for i in dup["issues"]), str(dup["issues"]))
    dd = next((i for i in dup["issues"] if i["rule"] == "duplicate-definition"), {})
    check("duplicate-definition keeps its term-specific explanation",
          dd.get("explanation") == "Mõiste «Müüja» on defineeritud 2 korda.", str(dd))
    check("definitions stays on every term",
          dup["defined_terms"][0]["definitions"] == 2
          and all("definitions" in t for t in d["defined_terms"]),
          str(dup["defined_terms"]))

    # long document under the raised cap does not raise
    big = "Käesoleva lepingu punkt 1. " * 20000  # ~540k? keep under cap
    big = big[:server.MAX_DOC_CHARS - 10]
    try:
        bd = server.check_defined_terms(big)
        check("accepts long doc under MAX_DOC_CHARS", True)
        check("a long doc is not echoed either", "text" not in bd, str(sorted(bd)))
    except Exception as e:
        check("accepts long doc under MAX_DOC_CHARS", False, str(e))
    # over the doc cap raises
    try:
        server.check_defined_terms("a" * (server.MAX_DOC_CHARS + 1))
        check("over MAX_DOC_CHARS raises", False, "no exception")
    except ValueError:
        check("over MAX_DOC_CHARS raises", True)


def defined_terms_quote_tests() -> None:
    print("check_defined_terms quote styles")
    # Estonian typography closes „ with “ (U+201C); that pairing used to
    # define nothing. Every pairing defines the same term, counted alike.
    styles = {
        "«»": ("«", "»"),
        "„“": ("„", "“"),
        "„”": ("„", "”"),
        '""': ('"', '"'),
        "“”": ("“", "”"),
    }
    for label, (o, c) in styles.items():
        r = server.check_defined_terms(
            f"Käesolev leping (edaspidi {o}Leping{c}) jõustub. Leping lõpeb 2027.")
        check(f"{label} defines Leping, used twice, no issues",
              r["defined_terms"] == [{"term": "Leping", "position": 17,
                                      "definitions": 1, "total_occurrences": 2}]
              and r["issues"] == [], str(r))

    # A „“ contract maps exactly like the same contract written with «».
    base = ('Käesoleva lepingu (edaspidi «Leping») pooled on AS Müük '
            '(edaspidi «Müüja») ja OÜ Ostja (edaspidi ühiselt «Pooled»). '
            'Müüja annab kauba üle. Leping jõustub. Kokkulepe (edaspidi '
            '«Kokkulepe») ja (edaspidi «Müüja»).')
    low = base.replace("«", "„").replace("»", "“")
    check("„“ document maps exactly like the «» one",
          server.check_defined_terms(low) == server.check_defined_terms(base),
          str(server.check_defined_terms(low)))

    # Two terms in one sentence, each in its own style, neither swallows
    # the other's closing quote.
    mixed = server.check_defined_terms(
        'AS Müük (edaspidi „Müüja“) ja OÜ Ost (edaspidi «Ostja») ning Pank '
        '(edaspidi “Pank”) sõlmivad lepingu. Müüja, Ostja ja Pank allkirjastavad.')
    terms = [t["term"] for t in mixed["defined_terms"]]
    check("mixed styles in one sentence define all three",
          terms == ["Müüja", "Ostja", "Pank"], str(mixed["defined_terms"]))
    check("no term holds a quote character",
          not any(set(t) & set("«»„“”\"") for t in terms), str(terms))
    check("mixed styles: every term used, no issues", mixed["issues"] == [], str(mixed["issues"]))

    # A multi-word term.
    sp = server.check_defined_terms(
        "AS Teenus (edaspidi „Teenuse osutaja“) osutab teenust. Teenuse osutaja vastutab.")
    check("„Teenuse osutaja“ is one term, used twice",
          sp["defined_terms"] == [{"term": "Teenuse osutaja", "position": 11,
                                   "definitions": 1, "total_occurrences": 2}]
          and sp["issues"] == [], str(sp))

    # A term defined in two quote styles is still one term, defined twice.
    dup = server.check_defined_terms(
        "Pool (edaspidi «Müüja») ja teine (edaspidi „Müüja“). Müüja tegutseb.")
    dd = next((i for i in dup["issues"] if i["rule"] == "duplicate-definition"), {})
    check("duplicate-definition across «» and „“",
          dd.get("explanation") == "Mõiste «Müüja» on defineeritud 2 korda."
          and dup["defined_terms"][0]["definitions"] == 2, str(dup))

    # defined-but-unused fires for a „“ definition as for a «» one.
    un = server.check_defined_terms("Käesolev kokkulepe (edaspidi „Kokkulepe“) jõustub täna.")
    check("„Kokkulepe“ unused → defined-but-unused",
          [i["rule"] for i in un["issues"]] == ["defined-but-unused"], str(un["issues"]))

    # 'ühiselt' and 'nimetatud' work with „“, and the bare form still does.
    pooled = server.check_defined_terms(
        "Müüja ja Ostja (edaspidi ühiselt nimetatud „Pooled“) lepivad kokku. Pooled kinnitavad.")
    check("edaspidi ühiselt nimetatud „Pooled“",
          [t["term"] for t in pooled["defined_terms"]] == ["Pooled"], str(pooled["defined_terms"]))
    bare = server.check_defined_terms("Käesolev leping (edaspidi nimetatud Leping) jõustub. Leping lõpeb.")
    check("bare 'edaspidi nimetatud Leping' still defines Leping",
          [t["term"] for t in bare["defined_terms"]] == ["Leping"], str(bare["defined_terms"]))
    # A missing space before the quote is still a definition.
    glued = server.check_defined_terms('Leping (edaspidi"Leping") jõustub. Leping lõpeb.')
    check('edaspidi"Leping" without a space still defines Leping',
          [t["term"] for t in glued["defined_terms"]] == ["Leping"], str(glued["defined_terms"]))

    # Estonian nests «» inside „“: the inner pair stays in the term.
    nest = server.check_defined_terms(
        "Programm (edaspidi „Programm «Kevad»“) algab. Programm «Kevad» lõpeb.")
    check("„Programm «Kevad»“ keeps its inner quotes",
          [(t["term"], t["total_occurrences"]) for t in nest["defined_terms"]]
          == [("Programm «Kevad»", 2)], str(nest["defined_terms"]))

    # 'edaspidi' closing a quotation is not a definition: “ and " close
    # there, so what follows them up to the next quote is not a term.
    for quoted in ('"Teen seda edaspidi", ütles ta. "Ei tee."',
                   "„Maksan edaspidi“, ütles ta ja lisas “aitäh”.",
                   "„Maksan edaspidi“, ütles ta. „Aitäh“, vastas teine."):
        q = server.check_defined_terms(quoted)
        check(f"no term from {quoted!r}", q["defined_terms"] == [] and q["issues"] == [], str(q))

    # A definition follows '(' or ','. The adverb 'edaspidi' before a
    # quotation (reported speech, emphasis, new wording) defines nothing,
    # in any quote style.
    for o, c in (("„", "“"), ("„", "”"), ("«", "»"), ('"', '"'), ("“", "”")):
        for adverbial in (f"Hageja väitis, et kostja lubas edaspidi {o}kõik võlad tasuda{c}, "
                          "kuid ei teinud seda.",
                          f"Pooled kohustuvad edaspidi {o}heas usus{c} läbirääkimisi pidama.",
                          f"Punkti 4.1 sõnastus on edaspidi {o}Üür on 650 eurot kuus{c}."):
            q = server.check_defined_terms(adverbial)
            check(f"no term from {adverbial[:40]!r}",
                  q["defined_terms"] == [] and q["issues"] == [], str(q))
        for lead in (f"AS Alfa, edaspidi {o}Müüja{c}, müüb. Müüja maksab.",
                     f"AS Alfa,\nedaspidi {o}Müüja{c}, müüb. Müüja maksab.",
                     f"AS Alfa ( edaspidi {o}Müüja{c}) müüb. Müüja maksab."):
            check(f"{lead[:28]!r} defines Müüja",
                  [t["term"] for t in server.check_defined_terms(lead)["defined_terms"]]
                  == ["Müüja"], str(server.check_defined_terms(lead)["defined_terms"]))

    # Uses are counted in one pass over the text, as a regex per term
    # counts them: a term inside a longer one still counts.
    nested = ("AS Alfa (edaspidi „Teenuse osutaja“) ja Teenuse (edaspidi „Teenuse“) lepivad "
              "kokku. Teenuse osutaja vastutab, Teenuse hind ja Teenuse-osutaja. Teenused.")
    want = {t: len(re.findall(r"(?<!\w)" + re.escape(t) + r"(?!\w)", nested))
            for t in ("Teenuse osutaja", "Teenuse")}
    got = {t["term"]: t["total_occurrences"]
           for t in server.check_defined_terms(nested)["defined_terms"]}
    check("a term inside a longer term is counted",
          got == want == {"Teenuse osutaja": 2, "Teenuse": 6}, str(got))
    # A regex per term made thousands of terms take seconds.
    many = "".join(f"(edaspidi „T{i}“) T{i}. " for i in range(6000))[:100_000]
    start = time.perf_counter()
    r = server.check_defined_terms(many)
    elapsed = time.perf_counter() - start
    check("thousands of terms stay fast", elapsed < 5 and len(r["defined_terms"]) > 3000
          and r["defined_terms"][0]["total_occurrences"] == 2, f"{elapsed:.1f} s")

    # An unclosed quote before a long blank run used to backtrack
    # quadratically (minutes at this size).
    start = time.perf_counter()
    server.check_defined_terms("Leping (edaspidi „Leping" + " " * 200_000)
    elapsed = time.perf_counter() - start
    check("unclosed quote before a long blank run stays linear", elapsed < 5, f"{elapsed:.1f} s")

    def found(text: str) -> list[tuple[str, int, int]]:
        r = server.check_defined_terms(text)
        return [(t["term"], t["definitions"], t["total_occurrences"]) for t in r["defined_terms"]]

    # An unclosed opener defines nothing and hides none of the definitions
    # after it, even with a straight or curly quote later in the text.
    for o in ("«", "„", '"'):
        broken = (f'AS Alfa (edaspidi {o}Müüja), OÜ Beeta (edaspidi «Ostja») ja AS Gamma '
                  '(edaspidi «Käendaja») sõlmisid käesoleva lepingu (edaspidi «Leping»). '
                  'Ostja tasub, Käendaja tagab ja Leping kehtib. Kaup tarnitakse OÜ "Delta" '
                  'ja “Smart” kaudu, ekraan 27".')
        r = server.check_defined_terms(broken)
        check(f"unclosed {o}Müüja) hides no later definition",
              found(broken) == [("Ostja", 1, 2), ("Käendaja", 1, 2), ("Leping", 1, 2)]
              and r["issues"] == [], str(r))
    # The same without parentheses: the term stops at the next 'edaspidi'.
    loose = ('AS Alfa, edaspidi «Müüja, ja OÜ Beeta, edaspidi «Ostja», sõlmivad '
             'lepingu. Ostja tasub OÜ "Delta" kaudu.')
    check("unclosed opener stops at the next edaspidi",
          found(loose) == [("Ostja", 1, 2)], str(found(loose)))
    # Nor does an unclosed opener with no stop at all become a term when
    # the next quote is far away.
    far = "Leping, edaspidi „Leping, " + "kehtib ja " * 30 + 'OÜ "Delta" kaudu.'
    check("unclosed opener with a distant quote defines nothing", found(far) == [], str(found(far)))

    # A doubled opener is a typo and is skipped.
    check("««Leping» defines Leping",
          found("Teenusleping (edaspidi ««Leping») jõustub. Leping lõpeb 2027.")
          == [("Leping", 1, 2)])
    dbl = ('Müüja (edaspidi ««Müüja»), Ostja (edaspidi «Ostja») ja Pank (edaspidi '
           '«Pank») sõlmivad lepingu. Müüja, Ostja ja Pank. Hoone asub aadressil "Pikk 1".')
    check("««Müüja» hides no later definition",
          found(dbl) == [("Müüja", 1, 3), ("Ostja", 1, 3), ("Pank", 1, 3)], str(found(dbl)))

    # Inner quotes around the whole term are double quoting, not the name;
    # an inner pair that starts the name stays.
    for o, c in (("„", "“"), ('"', '"'), ("“", "”")):
        r = server.check_defined_terms(
            f"Teenusleping (edaspidi {o}«Leping»{c}) jõustub. Leping lõpeb 2027.")
        check(f"{o}«Leping»{c} defines Leping, no issues",
              [(t["term"], t["total_occurrences"]) for t in r["defined_terms"]] == [("Leping", 2)]
              and r["issues"] == [], str(r))
    check("„'Leping'“ defines Leping",
          found("Teenusleping (edaspidi „'Leping'“) jõustub. Leping lõpeb.") == [("Leping", 1, 2)])
    green = "Linn (edaspidi „«Roheline linn» 2030“) algab. «Roheline linn» 2030 lõpeb."
    check("„«Roheline linn» 2030“ keeps its inner quotes",
          found(green) == [("«Roheline linn» 2030", 1, 2)], str(found(green)))

    # An apostrophe that belongs to the name stays in the term.
    for text, term in (("Kohvik (edaspidi «Kohvik 'Kodu'») avati. Kohvik 'Kodu' on avatud.",
                        "Kohvik 'Kodu'"),
                       ("Firma (edaspidi „Jones'“) maksab. Jones' esindaja allkirjastab.", "Jones'"),
                       ("Firma (edaspidi „McDonald’s“) maksab. McDonald’s esindaja kirjutab.",
                        "McDonald’s")):
        check(f"{term!r} keeps its apostrophe", found(text) == [(term, 1, 2)], str(found(text)))

    # Parentheses inside a term and a word starting with 'edaspidi' stay.
    for text, term in (("Hind (edaspidi „Hind (käibemaksuta)“) on lõplik. Hind (käibemaksuta) "
                        "tasutakse.", "Hind (käibemaksuta)"),
                       ("Kokkulepe (edaspidi „Edaspidise koostöö kokkulepe“) jõustub. "
                        "Edaspidise koostöö kokkulepe kehtib.", "Edaspidise koostöö kokkulepe")):
        check(f"{term!r} is one term", found(text) == [(term, 1, 2)], str(found(text)))


def is_legal_term_tests() -> None:
    print("_is_legal_term")
    check("solidaarvõlgnik is legal", server._is_legal_term("solidaarvõlgnik"))
    check("inflected võlasuhetele is legal", server._is_legal_term("võlasuhetele"))
    check("hagiavaldus (compound head) is legal", server._is_legal_term("hagiavaldus"))
    check("ordinary word 'koer' is not legal", not server._is_legal_term("koer"))
    check("ordinary word 'ilus' is not legal", not server._is_legal_term("ilus"))


def common_legal_usage_tests() -> None:
    print("common_legal_usage")
    r = server.common_legal_usage("kohustus")
    check("known legal term found", r["found"] is True, str(r.get("summary_estonian")))
    check("has a frequency", isinstance(r["frequency"], int) and r["frequency"] > 0, str(r["frequency"]))
    check("common_after is list of {word,count}",
          all("word" in x and "count" in x for x in r["common_after"]), str(r["common_after"]))
    after = {x["word"] for x in r["common_after"]}
    check("canonical 'kohustuse täitmine' present", "täitmine" in after, str(after))
    # The caller's word and a fixed note are not sent back.
    check("no word echo or note", "word" not in r and "note" not in r, str(sorted(r)))
    check("summary is the frequency sentence only",
          r["summary_estonian"] == f"'kohustus' esineb juriidilises korpuses {r['frequency']} korda.",
          r["summary_estonian"])

    # The summary names the index entry it counted: the lemma for an
    # inflected form, the word itself when only the fallback key matched.
    inflected = server.common_legal_usage("kohustuse")
    check("summary names the lemma", inflected["summary_estonian"].startswith("'kohustus' "),
          inflected["summary_estonian"])
    fallback = server.common_legal_usage("võime")
    check("summary names the matched entry on fallback",
          fallback["found"] and fallback["summary_estonian"].startswith("'võime' "),
          fallback["summary_estonian"])

    r2 = server.common_legal_usage("hagi")
    before = {x["word"] for x in r2["common_before"]}
    check("hagi has collocations", r2["found"] and (before or r2["common_after"]), str(r2))

    # Non-legal word → not found, empty lists, no crash.
    nf = server.common_legal_usage("koer")
    check("non-legal word → found False", nf["found"] is False, str(nf))
    check("not-found → empty collocations", nf["common_before"] == [] and nf["common_after"] == [])
    check("not-found: no word echo or note", "word" not in nf and "note" not in nf, str(sorted(nf)))
    check("not-found summary names the word", "'koer'" in nf["summary_estonian"], nf["summary_estonian"])

    # Single-word contract enforced.
    try:
        server.common_legal_usage("kaks sõna")
        check("rejects whitespace", False, "no exception")
    except ValueError:
        check("rejects whitespace", True)


legalese_tests()
defined_terms_tests()
defined_terms_quote_tests()
is_legal_term_tests()
common_legal_usage_tests()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall legal-tool tests passed")
