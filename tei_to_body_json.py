#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tei_to_body_json.py
Parses a TEI XML file (with namespaces) and exports the <text>/<body>
as a JSON structure suitable for a static SPA (index.html + app.js).

Usage:
  python tei_to_body_json.py input.xml -o body.json
"""

import argparse
import json
import html
from pathlib import Path

try:
    from lxml import etree
except ImportError as e:
    raise SystemExit(
        "This script requires lxml. Install it via:\n  pip install lxml"
    ) from e


XML_NS = "http://www.w3.org/XML/1998/namespace"
TEI_NS = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI_NS}


def esc(txt: str) -> str:
    return html.escape(txt, quote=False)


def lang_of(el) -> str:
    return el.get(f"{{{XML_NS}}}lang") or ""


def build_data_attrs(el) -> str:
    """Convert safe element attributes to data-* HTML attributes."""
    pairs = []
    for k, v in el.attrib.items():
        # Skip namespace decls and xml:lang (handled elsewhere)
        if k.startswith("{http://www.w3.org/2000/xmlns/}"):
            continue
        if k == f"{{{XML_NS}}}lang":
            continue
        # local attr name (strip namespace if any)
        if "}" in k:
            k = k.split("}", 1)[1]
        pairs.append(f'data-{html.escape(k)}="{esc(v)}"')
    return " ".join(pairs)


def serialize_inline(el) -> str:
    """
    Recursively serialize TEI inline-ish content to simple HTML.
    Unknown TEI elements become <span class="{local}">…</span>.
    """
    local = etree.QName(el).localname

    # textual content before children
    parts = []
    if el.text:
        parts.append(esc(el.text))

    # class building
    base_class = local
    typ = el.get("type")
    cls = f'{base_class} {base_class}-{typ}' if typ else base_class

    # data attributes (ref, key, ana, n, ident, etc.)
    data_attrs = build_data_attrs(el)
    data_attrs_str = f" {data_attrs}" if data_attrs else ""

    # Wrap recognized inline elements as <span>
    wrapper_start = f'<span class="{cls}"{data_attrs_str}>'
    wrapper_end = "</span>"

    inner = []
    for child in el:
        inner.append(serialize_element(child))
        if child.tail:
            inner.append(esc(child.tail))

    return wrapper_start + "".join(inner) + wrapper_end


def serialize_p(p_el) -> str:
    """Serialize a <p> element, preserving inline TEI structure."""
    lang = lang_of(p_el)
    lang_attr = f' lang="{esc(lang)}"' if lang else ""
    buf = []
    if p_el.text:
        buf.append(esc(p_el.text))
    for child in p_el:
        buf.append(serialize_element(child))
        if child.tail:
            buf.append(esc(child.tail))
    return f"<p{lang_attr}>" + "".join(buf) + "</p>"


def serialize_element(el) -> str:
    """Dispatch serializer for block vs inline."""
    qn = etree.QName(el)
    local = qn.localname
    ns = qn.namespace

    # Ignore comments, PIs
    if isinstance(el, etree._Comment):  # noqa: E721
        return ""
    if isinstance(el, etree._ProcessingInstruction):  # noqa: E721
        return ""

    # TEI namespace elements
    if ns == TEI_NS:
        if local == "p":
            return serialize_p(el)
        elif local in ("lb", "pb"):  # line/page breaks
            attrs = build_data_attrs(el)
            return f'<span class="{local}"{(" " + attrs) if attrs else ""}></span>'
        elif local == "note":
            # Keep notes inline; you could also collect separately.
            return serialize_inline(el)
        elif local == "div":
            # Divs handled at a higher level; if encountered inline, serialize contents
            inner = []
            if el.text:
                inner.append(esc(el.text))
            for ch in el:
                inner.append(serialize_element(ch))
                if ch.tail:
                    inner.append(esc(ch.tail))
            return "".join(inner)
        else:
            # default: inline wrapper span
            return serialize_inline(el)

    # Non-TEI elements: serialize as plain text + children
    parts = []
    if el.text:
        parts.append(esc(el.text))
    for child in el:
        parts.append(serialize_element(child))
        if child.tail:
            parts.append(esc(child.tail))
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Export TEI <body> to JSON for SPA use.")
    ap.add_argument("input", help="Input TEI XML")
    ap.add_argument("-o", "--output", default="body.json", help="Output JSON file")
    args = ap.parse_args()

    xml_path = Path(args.input)
    out_path = Path(args.output)

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(xml_path), parser=parser)
    root = tree.getroot()

    # Basic header metadata
    title_el = root.find(".//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title", NS)
    author_el = root.find(".//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:author", NS)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""
    author = author_el.text.strip() if author_el is not None and author_el.text else ""

    body = root.find(".//tei:text/tei:body", NS)
    if body is None:
        raise SystemExit("No <text>/<body> found in TEI.")

    divs_payload = []
    for div in body.findall("tei:div", NS):
        div_type = div.get("type", "")
        n = div.get("n", "")
        # Serialize children <p> etc. into one HTML block
        html_parts = []
        if div.text and div.text.strip():
            html_parts.append(esc(div.text))
        for child in div:
            html_parts.append(serialize_element(child))
            if child.tail:
                html_parts.append(esc(child.tail))
        divs_payload.append(
            {
                "n": n,
                "type": div_type,
                "html": "".join(html_parts),
            }
        )

    payload = {
        "meta": {
            "title": title,
            "author": author,
            "generatedFrom": xml_path.name,
        },
        "divs": divs_payload,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(divs_payload)} divs).")


if __name__ == "__main__":
    main()
