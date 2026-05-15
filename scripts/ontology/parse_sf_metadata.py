from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .models import SFField, SFObject, SFPicklistValue, SFRelationship

NS = "{http://soap.sforce.com/2006/04/metadata}"


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _bool(el: ET.Element | None) -> bool:
    return _text(el).lower() == "true"


def _int(el: ET.Element | None) -> int | None:
    t = _text(el)
    return int(t) if t else None


def _extract_namespace(api_name: str) -> str:
    parts = api_name.split("__")
    if len(parts) >= 3:
        return parts[0]
    return ""


def parse_field_xml(path: Path) -> SFField:
    tree = ET.parse(path)
    root = tree.getroot()

    picklist_values: list[SFPicklistValue] = []
    value_set = root.find(f"{NS}valueSet")
    if value_set is not None:
        for vsd in value_set.findall(f"{NS}valueSetDefinition/{NS}value"):
            picklist_values.append(
                SFPicklistValue(
                    api_name=_text(vsd.find(f"{NS}fullName")),
                    label=_text(vsd.find(f"{NS}label")),
                    is_default=_bool(vsd.find(f"{NS}default")),
                )
            )

    return SFField(
        api_name=_text(root.find(f"{NS}fullName")),
        label=_text(root.find(f"{NS}label")),
        type=_text(root.find(f"{NS}type")),
        required=_bool(root.find(f"{NS}required")),
        description=_text(root.find(f"{NS}description")),
        reference_to=_text(root.find(f"{NS}referenceTo")) or None,
        relationship_name=_text(root.find(f"{NS}relationshipName")) or None,
        relationship_label=_text(root.find(f"{NS}relationshipLabel")) or None,
        delete_constraint=_text(root.find(f"{NS}deleteConstraint")) or None,
        picklist_values=picklist_values,
        length=_int(root.find(f"{NS}length")),
        precision=_int(root.find(f"{NS}precision")),
        scale=_int(root.find(f"{NS}scale")),
        external_id=_bool(root.find(f"{NS}externalId")),
        unique=_bool(root.find(f"{NS}unique")),
    )


def parse_object_dir(obj_dir: Path) -> SFObject | None:
    api_name = obj_dir.name
    obj_meta = obj_dir / f"{api_name}.object-meta.xml"

    label = ""
    plural_label = ""
    description = ""
    sharing_model = ""

    if obj_meta.exists():
        tree = ET.parse(obj_meta)
        root = tree.getroot()
        label = _text(root.find(f"{NS}label"))
        plural_label = _text(root.find(f"{NS}pluralLabel"))
        description = _text(root.find(f"{NS}description"))
        sharing_model = _text(root.find(f"{NS}sharingModel"))

    fields: list[SFField] = []
    fields_dir = obj_dir / "fields"
    if fields_dir.exists():
        for fpath in sorted(fields_dir.glob("*.field-meta.xml")):
            try:
                fields.append(parse_field_xml(fpath))
            except ET.ParseError:
                continue

    relationships: list[SFRelationship] = []
    for f in fields:
        if f.is_relationship and f.reference_to:
            relationships.append(
                SFRelationship(
                    field_api_name=f.api_name,
                    source_object=api_name,
                    target_object=f.reference_to,
                    relationship_type=f.type,
                    relationship_name=f.relationship_name or "",
                    relationship_label=f.relationship_label or "",
                    delete_constraint=f.delete_constraint or "",
                    description=f.description,
                )
            )

    record_types: list[str] = []
    rt_dir = obj_dir / "recordTypes"
    if rt_dir.exists():
        for rt_path in sorted(rt_dir.glob("*.recordType-meta.xml")):
            name = rt_path.stem.removesuffix(".recordType-meta")
            for ns in ("LLC_BI__", "nFORCE__"):
                name = name.removeprefix(ns)
            record_types.append(name.replace("_", " "))

    return SFObject(
        api_name=api_name,
        label=label,
        plural_label=plural_label,
        namespace=_extract_namespace(api_name),
        description=description,
        sharing_model=sharing_model,
        fields=fields,
        relationships=relationships,
        record_types=record_types,
    )


def parse_all_objects(
    metadata_root: Path, object_filter: list[str] | None = None
) -> dict[str, SFObject]:
    objects: dict[str, SFObject] = {}

    for obj_dir in sorted(metadata_root.iterdir()):
        if not obj_dir.is_dir():
            continue
        if object_filter and obj_dir.name not in object_filter:
            continue
        obj = parse_object_dir(obj_dir)
        if obj:
            objects[obj.api_name] = obj

    _resolve_incoming_relationships(objects)
    return objects


def _resolve_incoming_relationships(objects: dict[str, SFObject]) -> None:
    for obj in objects.values():
        for rel in obj.relationships:
            target = objects.get(rel.target_object)
            if target:
                target.incoming_relationships.append(rel)
