#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tei_to_body_json_stdlib.py
Parse TEI (with namespaces) using only Python's standard library and export <text>/<body> to body.json.
Adds commentaryHtml (from tei:note) and apparatusHtml (from tei:app), and collects witnesses for a specimen panel.
Usage:
  python tei_to_body_json_stdlib.py input.xml -o body.json
"""
import argparse
import json
import html
from pathlib import Path
from xml.etree import ElementTree as ET

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS}

def esc(txt: str) -> str:
    return html.escape(txt or "", quote=False)

def get_local(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

def build_data_attrs(el) -> str:
    pairs = []
    for k, v in el.attrib.items():
        if k.startswith("{http://www.w3.org/2000/xmlns/}"):
            continue
        if k == f"{{{XML_NS}}}lang":
            continue
        if "}" in k:
            k = k.split("}", 1)[1]
        pairs.append(f'data-{esc(k)}="{esc(v)}"')
    return " ".join(pairs)

def serialize_inline(el) -> str:
    local = get_local(el.tag)
    base_class = local
    typ = el.attrib.get("type")
    cls = f"{base_class} {base_class}-{typ}" if typ else base_class
    data_attrs = build_data_attrs(el)
    buf = []
    if el.text:
        buf.append(esc(el.text))
    for child in el:
        buf.append(serialize_element(child))
        if child.tail:
            buf.append(esc(child.tail))
    inner_html = "".join(buf)
    attr = f" {data_attrs}" if data_attrs else ""
    return f'<span class="{cls}"{attr}>' + inner_html + "</span>"

def serialize_p(p_el) -> str:
    lang = p_el.get(f"{{{XML_NS}}}lang") or ""
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
    qn_local = get_local(el.tag)
    if el.tag.startswith("{"+TEI_NS+"}"):
        if qn_local == "p":
            return serialize_p(el)
        elif qn_local in ("lb","pb","cb"):
            attrs = build_data_attrs(el)
            return f'<span class="{qn_local}"' + (" " + attrs if attrs else "") + "></span>"
        elif qn_local == "div":
            inner = []
            if el.text:
                inner.append(esc(el.text))
            for ch in el:
                inner.append(serialize_element(ch))
                if ch.tail:
                    inner.append(esc(ch.tail))
            return "".join(inner)
        elif qn_local == "note":
            return ""  # excluded from main flow; collected separately
        else:
            return serialize_inline(el)
    parts = []
    if el.text:
        parts.append(esc(el.text))
    for child in el:
        parts.append(serialize_element(child))
        if child.tail:
            parts.append(esc(child.tail))
    return "".join(parts)

def inner_serialized_text(el) -> str:
    parts = []
    if el is None:
        return ""
    if el.text:
        parts.append(esc(el.text))
    for ch in el:
        parts.append(serialize_element(ch))
        if ch.tail:
            parts.append(esc(ch.tail))
    return "".join(parts)

def normalize_wit(wit_str: str) -> str:
    if not wit_str:
        return ""
    sigla = []
    for token in wit_str.split():
        t = token.lstrip("#").strip()
        if not t:
            continue
        if t.upper() == "AI":
            sigla.append("AI (ed.)")
        else:
            sigla.append(t)
    return " ".join(sigla)

def extract_commentary(div_el) -> str:
    notes = div_el.findall(".//tei:note", NS)
    if not notes:
        return ""
    out = []
    for n in notes:
        data_attrs = build_data_attrs(n)
        attr = f' {data_attrs}' if data_attrs else ""
        content = inner_serialized_text(n)
        out.append(f'<p class="note"{attr}>{content}</p>')
    return "\n".join(out)

def extract_apparatus(div_el) -> str:
    apps = div_el.findall(".//tei:app", NS)
    if not apps:
        return ""
    items = []
    for ap in apps:
        lem_el = ap.find("tei:lem", NS)
        rdgs = ap.findall("tei:rdg", NS)
        lem_html = inner_serialized_text(lem_el)
        rdg_bits = []
        for r in rdgs:
            wit = normalize_wit(r.get("wit", ""))
            txt = inner_serialized_text(r)
            wit_html = f'<span class="wit">{wit}</span>' if wit else ""
            rdg_bits.append((wit_html + (" " if (wit_html and txt) else "") + txt).strip())
        joined = " &#x203A; ".join(rdg_bits)  # ›
        items.append(f'<div class="app-item"><span class="lem">{lem_html}</span> : {joined}</div>')
    return "\n".join(items)

def extract_witnesses(root) -> list:
    wits = []
    for w in root.findall(".//tei:listWit/tei:witness", NS):
        wid = w.get(f"{{http://www.w3.org/XML/1998/namespace}}id") or ""
        text = "".join(w.itertext()).strip()
        wits.append({"id": wid, "text": text})
    return wits

def main():
    ap = argparse.ArgumentParser(description="Export TEI <body> to JSON (with commentary/apparatus).")
    ap.add_argument("input", help="Input TEI XML")
    ap.add_argument("-o", "--output", default="body.json", help="Output JSON file")
    args = ap.parse_args()

    input_xml = Path(args.input)
    out_path = Path(args.output)

    tree = ET.parse(str(input_xml))
    root = tree.getroot()

    title_el = root.find(".//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title", NS)
    author_el = root.find(".//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:author", NS)
    title = (title_el.text or "").strip() if title_el is not None else ""
    author = (author_el.text or "").strip() if author_el is not None else ""

    witnesses = extract_witnesses(root)

    body = root.find(".//tei:text/tei:body", NS)
    if body is None:
        raise SystemExit("No <text>/<body> found in TEI.")

    divs_payload = []
    for div in body.findall("tei:div", NS):
      n = div.attrib.get("n","")
      typ = div.attrib.get("type","")
      html_parts = []
      if div.text and div.text.strip():
          html_parts.append(esc(div.text))
      for ch in list(div):
          html_parts.append(serialize_element(ch))
          if ch.tail:
              html_parts.append(esc(ch.tail))

      commentary_html = extract_commentary(div)
      apparatus_html = extract_apparatus(div)

      divs_payload.append({
          "n": n,
          "type": typ,
          "html": "".join(html_parts),
          "commentaryHtml": commentary_html,
          "apparatusHtml": apparatus_html,
      })

    payload = {
        "meta": {"title": title, "author": author, "generatedFrom": input_xml.name, "witnesses": witnesses},
        "divs": divs_payload
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(payload['divs'])} divs).")

if __name__ == "__main__":
    main()
