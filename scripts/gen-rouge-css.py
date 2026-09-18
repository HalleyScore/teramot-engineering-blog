#!/usr/bin/env python3
"""Generate assets/css/custom.css: Rouge syntax colors matching Blowfish's Chroma.

Markdown code blocks are highlighted by Hugo's Chroma; AsciiDoc code blocks are
highlighted by Asciidoctor's Rouge (see config/_default/markup.toml). Both emit
the same Pygments token classes (.k, .nf, .s1, ...), so the two differ only in
the wrapper: Chroma marks it <pre class="chroma">, Rouge <pre class="rouge">.

This script lifts the theme's generated Chroma palettes -- light and dark --
and re-points them at Rouge's wrapper, so both formats render identically in
both appearances without a second colour scheme to maintain.

Re-run after upgrading the Blowfish submodule:

    python3 scripts/gen-rouge-css.py
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "themes/blowfish/assets/css/components/chroma.css"
OUT = ROOT / "assets/css/custom.css"

# The theme scopes its two palettes with these selectors. Rules are emitted
# flattened rather than nested: custom.css is concatenated and minified but
# never run through PostCSS, so native CSS nesting would survive into the
# bundle and would only work in browsers that support it. The theme's own
# compiled CSS is flat, so this matches it exactly.
SCOPES = (
    ("html:not(.dark) {", "html:not(.dark)"),
    ("html.dark {", "html.dark"),
)

# Chroma-only line-numbering constructs that Rouge never emits.
CHROMA_ONLY = re.compile(r"\.chroma \.(lntd|lntable|lnlinks|lnt|ln|line|hl)\b")

# `.bg` is not scoped to the highlighter and the theme already defines it.
UNSCOPED_BG = re.compile(r"(?<![\w.-])\.bg\s*\{")

# Rouge emits a few coarser tokens than Chroma does for the same construct, so
# the theme's palette has no rule for them. Map each to its nearest Chroma
# equivalent, or those spans would silently fall back to the body text colour.
# Applied only when the alias is genuinely missing and its target is present.
ALIASES = {"n": "nx"}  # Name -> NameOther (bare identifiers)

BEGIN = "/* BEGIN GENERATED: rouge syntax highlighting (scripts/gen-rouge-css.py) */"
END = "/* END GENERATED: rouge syntax highlighting */"

HEADER = """/* -- Rouge Highlight (AsciiDoc) -- */
/* Everything between the BEGIN/END markers is GENERATED -- do not edit by hand.
 *
 * Asciidoctor highlights .adoc code blocks with Rouge, which emits the same
 * Pygments token classes as Chroma but wraps them in <pre class="rouge">
 * instead of <pre class="chroma">. These rules are the theme's own Chroma
 * palettes re-pointed at that wrapper, so AsciiDoc and Markdown code blocks
 * are coloured identically in light and dark mode.
 *
 * Padding, rounding and overflow are not set here: both formats sit inside
 * the same prose styles and inherit them.
 *
 * Source: themes/blowfish/assets/css/components/chroma.css
 * Regenerate after upgrading the theme: python3 scripts/gen-rouge-css.py
 */
"""

RULE = re.compile(r"^(?P<comment>/\*.*?\*/\s*)?(?P<body>.+)$")


def extract(css: str, opener: str) -> str:
    """Return the body of a top-level `opener { ... }` block."""
    start = css.index(opener) + len(opener)
    depth = 1
    for i in range(start, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i]
    raise ValueError(f"unbalanced braces after {opener!r}")


def convert(body: str, scope: str) -> list[str]:
    rules = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line or UNSCOPED_BG.search(line) or CHROMA_ONLY.search(line):
            continue
        line = re.sub(r"\.chroma\b", "pre.rouge", line)
        # Comment-only lines (the palette's provenance banner) carry no rule;
        # prefixing one with a scope would emit a selector with no block.
        if re.fullmatch(r"/\*.*?\*/", line):
            rules.append(line)
            continue
        m = RULE.match(line)
        rules.append(f"{m['comment'] or ''}{scope} {m['body']}")
    return rules


def add_aliases(rules: list[str], scope: str) -> list[str]:
    joined = "\n".join(rules)
    for alias, target in ALIASES.items():
        if re.search(rf"pre\.rouge \.{alias}\s*\{{", joined):
            continue
        m = re.search(rf"pre\.rouge \.{target}\s*\{{([^}}]*)\}}", joined)
        if not m:
            continue
        rules.append(
            f"/* Name (Rouge) -> as Chroma's .{target} */ "
            f"{scope} pre.rouge .{alias} {{{m.group(1)}}}"
        )
    return rules


def main() -> int:
    if not SRC.exists():
        sys.exit(f"{SRC} not found -- is the Blowfish submodule checked out?")
    css = SRC.read_text()

    out = [HEADER]
    for opener, scope in SCOPES:
        rules = add_aliases(convert(extract(css, opener), scope), scope)
        out.append("\n".join(rules) + "\n")

    block = "\n".join([BEGIN, *out, END])

    # custom.css is hand-maintained (fonts, branding, layout); only the marked
    # region belongs to this script. Replace it in place, or append it once.
    existing = OUT.read_text() if OUT.exists() else ""
    if BEGIN in existing and END in existing:
        head, rest = existing.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        updated = f"{head}{block}{tail}"
        action = "updated generated block in"
    else:
        sep = "" if existing.endswith("\n\n") or not existing else "\n"
        updated = f"{existing}{sep}\n{block}\n"
        action = "appended generated block to"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(updated)
    print(f"{action} {OUT.relative_to(ROOT)} ({block.count(chr(10)) + 1} lines generated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
