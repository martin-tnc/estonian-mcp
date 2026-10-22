"""Every tool's real output must satisfy the schema it advertises.

This exists because `paradigm` answered `isError` to every MCP client for
two weeks and nothing here noticed. The tool functions were fine, the
tests called them directly, and the failure lived in the layer between:
the SDK built the structured payload from the tool's output schema and
filled every DECLARED BUT ABSENT key with None before validating. A field
typed `str` in a `total=False` TypedDict then failed as "None is not of
type 'string'", and the caller got an error instead of a paradigm. Since
0.8.0 the server keeps only the keys a tool returned (_EstonianMCP), and
this file also checks that wire format: one compact text block that says
what structuredContent says, and no null a tool did not write.

Calling the python function proves nothing about that, and neither does
`mcp.call_tool`, which does not validate. So this test does what a client
does: read the advertised schema, run the tool, and check the structured
payload against it.

Run via:

    uv run python tests/test_output_schemas.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jsonschema

import server

# A glossary exported in the developer's shell would change what these
# tools return; the suite checks the server as it ships. The
# glossary is read on first use, so this is early enough.
for _name in ("ESTNLTK_MCP_DOMAIN_GLOSSARY", "ESTNLTK_MCP_DOMAIN_IDENTIFIERS",
              "ESTNLTK_MCP_DOMAIN_SUGGEST_CUTOFF"):
    os.environ.pop(_name, None)

failures: list[str] = []
skipped: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"  FAIL {label} {detail}")


# One representative call per tool, plus the shapes that take a different
# path through the code. `paradigm` gets six: the bug that prompted this
# file only appeared for words whose result OMITS an optional key, which
# is most of them, and the omitted set differs per word.
CALLS: list[tuple[str, dict]] = [
    ("tokenize", {"text": "Tere maailm. Teine lause."}),
    ("lemmatize", {"text": "Koerad jooksevad."}),
    ("pos_tag", {"text": "Koerad jooksevad."}),
    ("analyze_morphology", {"text": "Läksin majja."}),
    ("analyze_morphology", {"text": "Ta on kodus.", "all_analyses": True}),
    ("spell_check", {"text": "Tere maailmm"}),   # a misspelled row
    ("spell_check", {"text": "Tere maailm."}),   # clean: an empty list
    ("syllabify", {"word": "koerad"}),
    ("named_entities", {"text": "Tallinn on Eesti pealinn."}),
    ("paradigm", {"word": "maja"}),          # single paradigm, most keys absent
    ("paradigm", {"word": "kott"}),          # two paradigms, key + others present
    ("paradigm", {"word": "kaunis"}),        # promoted reading
    ("paradigm", {"word": "kasutama"}),      # verb table
    ("paradigm", {"word": "ja"}),            # does not inflect
    ("paradigm", {"word": "qwertyxyz"}),     # not analysable
    ("classify_register", {"text": "Käesoleva lepingu alusel sätestatakse kohustused."}),
    ("check_style", {"text": "Süsteem kasutab andmeid. Andmed töödeldakse."}),
    ("check_officialese", {"text": "Aruandeperioodil koguti ja valideeriti andmestik."}),
    ("check_term_consistency", {"text": "Andmestik ja teadusandmestik."}),
    ("check_term_consistency", {"text": "Andmestik ja teadusandmestik.",
                                "glossary": ["teadusandmestik"]}),  # preferred
    ("check_compounds", {"text": "Kooli maja on suur."}),
    ("check_punctuation", {"text": "Ma tean et see on hea."}),
    ("check_capitalization", {"text": "Olen Eestlane."}),
    ("check_numbers", {"text": "Pi on 3.14."}),
    ("check_redundancy", {"text": "Samuti ka."}),
    ("check_object_case", {"text": "Ma ei näen koera."}),
    ("check_abbreviation_hyphenation", {"text": "MCPst tuleb abi."}),
    ("check_compound_familiarity", {"text": "See on mõtteliin."}),
    ("check_domain_terms", {"text": "See on mõtteliin."}),
    ("check_domain_terms", {"text": "Vagunisõit ja vagunireisitabel.",
                            "glossary": ["vagunireis"]}),  # suggestions
    ("check_hyphenation", {"word": "koerad"}),
    ("check_legalese", {"text": "Käesolev leping."}),
    ("check_defined_terms", {"text": 'Müüja (edaspidi «Müüja») müüb kauba.'}),
    ("common_legal_usage", {"word": "hagi"}),
    ("synonyms", {"word": "kohv"}),                 # needs WordNet
    ("find_related_words", {"word": "kohv"}),       # needs fastText
]

# These need a downloaded resource. Absent, the tool raises on purpose and
# that is the resource tests' business, not this file's.
NEEDS_RESOURCES = {"synonyms", "find_related_words"}


async def run() -> None:
    tools = {t.name: t for t in await server.mcp.list_tools()}

    print("every registered tool has an output schema")
    for name, tool in sorted(tools.items()):
        check(f"{name} advertises one", tool.outputSchema is not None)

    print("and the structured payload a client receives satisfies it")
    for name, args in CALLS:
        tool = tools.get(name)
        if tool is None:
            check(f"{name} is registered", False, "not in list_tools()")
            continue
        label = f"{name}({next(iter(args.values()))!r})"
        try:
            _content, structured = await server.mcp.call_tool(name, args)
        except Exception as e:
            if name in NEEDS_RESOURCES:
                skipped.append(f"{label}: {type(e).__name__}")
                print(f"  SKIP {label} (needs a downloaded resource)")
                continue
            check(label, False, f"raised {type(e).__name__}: {str(e)[:90]}")
            continue
        try:
            jsonschema.validate(structured, tool.outputSchema)
            print(f"  PASS {label}")
        except jsonschema.ValidationError as e:
            path = "/".join(str(p) for p in e.absolute_path) or "(root)"
            check(label, False, f"schema violation at {path}: {e.message[:90]}")

    print("no tool answers isError for a valid call")
    # The layer turns a schema violation into an error RESULT rather than an
    # exception, which is why this was invisible: the server stayed up, the
    # tests stayed green, and every caller got an error string.
    for name, args in CALLS:
        if name in NEEDS_RESOURCES:
            continue
        content, _structured = await server.mcp.call_tool(name, args)
        text = ""
        if content and getattr(content[0], "text", None):
            text = content[0].text
        check(f"{name} returns a result, not an error string",
              "Output validation error" not in text, text[:100])

    print("the wire format is lean")
    # Every caller pays for these bytes in tokens; see _EstonianMCP. One
    # compact block, saying exactly what structuredContent says.
    for name, args in CALLS:
        if name in NEEDS_RESOURCES:
            continue
        label = f"{name}({next(iter(args.values()))!r})"
        content, structured = await server.mcp.call_tool(name, args)
        text = content[0].text if content else ""
        check(f"{label} answers in one text block", len(content) == 1, str(len(content)))
        payload = json.loads(text)
        check(f"{label} text is compact JSON",
              text == json.dumps(payload, ensure_ascii=False, separators=(",", ":")), text[:80])
        # List tools are wrapped as {"result": [...]} in structuredContent,
        # which the outputSchema requires; the text is the bare list.
        expected = structured["result"] if isinstance(payload, list) else structured
        check(f"{label} text equals structuredContent", payload == expected, text[:80])
    # The SDK default filled each declared-but-absent key with null, which
    # Claude Code shows the model. paradigm('maja') omits several keys.
    _content, structured = await server.mcp.call_tool("paradigm", {"word": "maja"})
    raw = server.paradigm("maja")
    check("structuredContent carries only the keys the tool returned",
          set(structured) == set(raw), str(sorted(set(structured) ^ set(raw))))
    # spell_check lists only misspelled words, so clean text, its most
    # common result, is an empty list. A client that reads only the text
    # must still get an answer, not a blank result.
    content, structured = await server.mcp.call_tool("spell_check", {"text": "Tere maailm."})
    check("clean spell_check text answers one '[]' block",
          [c.text for c in content] == ["[]"] and structured == {"result": []},
          f"{[c.text for c in content]} {structured}")
    content, structured = await server.mcp.call_tool("spell_check", {"text": "Tere maailmm"})
    check("a misspelling comes back as one populated row",
          [r["text"] for r in structured["result"]] == ["maailmm"]
          and structured["result"][0]["spelling"] is False, str(structured))

    print("advertised schemas carry no title noise")

    def titles(node, path=""):
        # A property NAMED "title" is data; only the annotation counts.
        if isinstance(node, list):
            return [t for i, x in enumerate(node) for t in titles(x, f"{path}/{i}")]
        if not isinstance(node, dict):
            return []
        found = [path] if isinstance(node.get("title"), str) else []
        for key, value in node.items():
            if key in ("properties", "$defs") and isinstance(value, dict):
                found += [t for n, sub in value.items() for t in titles(sub, f"{path}/{key}/{n}")]
            elif key != "title":
                found += titles(value, f"{path}/{key}")
        return found

    for name, tool in sorted(tools.items()):
        left = titles(tool.inputSchema) + titles(tool.outputSchema or {})
        check(f"{name} schemas have no title", not left, str(left[:3]))

    print("descriptions arrive unwrapped and dedented")
    # Hard wrapping and docstring indentation cost tokens and say nothing.
    # A line break inside a paragraph is allowed only before a list item.
    for name, tool in sorted(tools.items()):
        bad = [line for block in tool.description.split("\n\n")
               for line in block.split("\n")[1:] if not server._LIST_ITEM.match(line)]
        bad += [line for line in tool.description.split("\n") if line != line.strip()]
        check(f"{name} description is reflowed", not bad, str(bad[:2]))

    print("the server instructions carry the rules the tools no longer repeat")
    # Per-tool notes and docstrings stopped repeating these in 0.8.0, on the
    # strength of saying each once here. Losing one loses the steering.
    instr = server.SERVER_INSTRUCTIONS
    for needle in ("_estonian", "verbatim", "heuristics", "empty list",
                   "does not apply is omitted", f"{server.MAX_TEXT_CHARS:,}",
                   f"{server.MAX_DOC_CHARS:,}", "check_compound_familiarity"):
        check(f"instructions mention {needle!r}", needle in instr)
    check("instructions stay well under Claude Code's 4,096-character cut",
          len(instr) < 3000, str(len(instr)))

    print("every tool in the registry is exercised here")
    registered = set(tools)
    covered = {name for name, _ in CALLS}
    missing = registered - covered
    check("no tool is left untested", not missing, str(sorted(missing)))


asyncio.run(run())

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
if skipped:
    print(f"\n{len(skipped)} call(s) skipped for missing resources:")
    for s in skipped:
        print(" -", s)
print("\nall output-schema tests passed")
