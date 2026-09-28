from __future__ import annotations

import xml.etree.ElementTree as ET


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def text_map(element: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in element.iter():
        if child is element:
            continue
        name = local_name(child.tag)
        value = (child.text or "").strip()
        if value and name not in out:
            out[name] = value
    return out


def parse_items(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items = []
    for elem in root.iter():
        if local_name(elem.tag) == "item":
            items.append(text_map(elem))
    return items


def first_text(xml_text: str, names: tuple[str, ...]) -> str:
    root = ET.fromstring(xml_text)
    wanted = set(names)
    for elem in root.iter():
        if local_name(elem.tag) in wanted:
            value = (elem.text or "").strip()
            if value:
                return value
    return ""
