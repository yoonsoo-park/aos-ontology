from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SFPicklistValue:
    api_name: str
    label: str
    is_default: bool = False


@dataclass
class SFField:
    api_name: str
    label: str
    type: str
    required: bool = False
    description: str = ""
    reference_to: str | None = None
    relationship_name: str | None = None
    relationship_label: str | None = None
    delete_constraint: str | None = None
    picklist_values: list[SFPicklistValue] = field(default_factory=list)
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    external_id: bool = False
    unique: bool = False

    @property
    def is_relationship(self) -> bool:
        return self.type in ("Lookup", "MasterDetail", "Hierarchy")


@dataclass
class SFRelationship:
    field_api_name: str
    source_object: str
    target_object: str
    relationship_type: str
    relationship_name: str
    relationship_label: str
    delete_constraint: str = ""
    description: str = ""


@dataclass
class SFObject:
    api_name: str
    label: str
    plural_label: str = ""
    namespace: str = ""
    description: str = ""
    sharing_model: str = ""
    fields: list[SFField] = field(default_factory=list)
    relationships: list[SFRelationship] = field(default_factory=list)
    incoming_relationships: list[SFRelationship] = field(default_factory=list)
    record_types: list[str] = field(default_factory=list)

    @property
    def clean_label(self) -> str:
        return self.label or self._label_from_api_name()

    def _label_from_api_name(self) -> str:
        name = self.api_name
        for ns in ("LLC_BI__", "nFORCE__", "nFORMS__", "nSBA__", "FinServ__"):
            name = name.removeprefix(ns)
        return name.removesuffix("__c").removesuffix("__mdt").replace("_", " ")
