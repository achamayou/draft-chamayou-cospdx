#!/usr/bin/env python3

"""
TODO:

- Add cut operator at least in allOf contexts to avoid over-approximations
- Add sockets to AnyClass and SHACLClass for future extension
"""

import json
import re
import sys
import pathlib


def traverse(schema):
    for key, value in schema.items():
        if isinstance(value, dict):
            yield from traverse(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield from traverse(item)
        else:
            yield key, value


def refs(node):
    count = 0
    for key, _ in traverse(node):
        if key == "$ref":
            count += 1
    return count


def totalrefs(name, defs):
    count = 0
    seen = set()
    unresolved = {name}
    while unresolved:
        node_name = unresolved.pop()
        seen.add(node_name)
        node = defs[node_name]
        for key, value in traverse(node):
            if key == "$ref":
                count += 1
                refname = value.split("/")[-1]
                if refname not in seen:
                    unresolved.add(refname)
    return count


def types_with_no_refs(schema):
    return {name: node for name, node in schema["$defs"].items() if refs(node) == 0}


def stats(schema):
    print(f"; {len(schema['$defs'])} definitions")
    print(f"; {refs(schema)} references")
    types_with_no_refs_count = len(types_with_no_refs(schema))
    print(f"; {types_with_no_refs_count} types with no references")
    print()


def declaration(name, schema, klass):
    return f"{name} = {klass.cddl(schema)}"


class StringType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "string" and {
            "type",
            "pattern",
            "allOf",
        }.issuperset(schema.keys())

    @staticmethod
    def cddl(schema):
        def escape_pattern(pattern):
            return pattern.replace("\\", "\\\\")

        if "pattern" in schema:
            # \ needs to be escaped in CDDL regexps
            pattern = escape_pattern(schema["pattern"])
            return f'tstr .regexp "{pattern}"'

        if "allOf" in schema:
            patterns = []
            for value in schema["allOf"]:
                assert value.keys() == {"pattern"}
                pattern = escape_pattern(value["pattern"])
                patterns.append(f'tstr .regexp "{pattern}"')
            return " / ".join(patterns)

        return "tstr"


class ContiguousInternedEntries:
    def __init__(self, prefix, offset):
        self.prefix = prefix
        self.starting_offset = offset
        self.latest_index = offset
        self.entries = {}
        self.unescaped_entries = set()

    def escape_name(self, name):
        # The space of possible JSON strings is greater than valid CDDL identifiers.
        # This is not a general escaping mechanism, but aims to cover SPDX values,
        # and keeps track of already-escaped entries to detect any collisions.
        escaped = name.replace(":", "_").replace("/", "_")
        if escaped in self.entries and escaped not in self.unescaped_entries:
            raise ValueError(f"Name collision after escaping: {name} -> {escaped}")
        self.unescaped_entries.add(escaped)
        return escaped

    def get(self, entry):
        interned_name = self.escape_name(f"{self.prefix}.{entry}")
        if not interned_name in self.entries:
            self.latest_index += 1
            self.entries[interned_name] = self.latest_index
        return interned_name

    def definitions(self):
        return "\n".join(
            [
                f"{name} = {index}"
                for name, index in sorted(self.entries.items(), key=lambda x: x[1])
            ]
        )

    def description(self):
        return f"Value mapping for {self.prefix} entries ({self.starting_offset}-{self.latest_index})"


class ContiguousInternedLabels(ContiguousInternedEntries):
    def __init__(self, prefix, offset):
        super().__init__(prefix, offset)

    def definitions(self, grouping):
        text = ""
        for name, index in sorted(self.entries.items(), key=lambda x: x[1]):
            prefix, full_name = name.split(".", 1)
            assert prefix == self.prefix
            if "_" in full_name:
                profile, property = full_name.split("_", 1)
                profile = grouping.to_profile(profile)
            else:
                profile = "Core"
                property = full_name
            if not (full_name.startswith("@") or full_name == "type"):
                text += f"; https://spdx.github.io/spdx-spec/v3.0.1/model/{profile}/Properties/{property}/\n"
            text += f"{name} = {index}\n"
        return text.strip()


LABELS = ContiguousInternedLabels("label", 0)
CONSTS = ContiguousInternedEntries("const", 1000)


def drop_weaker_constraints(seq):
    parts = seq.split(", ")
    defined = set()
    weaker = {}
    pos = 0
    for part in parts:
        if " => " in part:
            label, value = part.split(" => ")
            if label.startswith("?"):
                weaker[label[1:]] = pos
            elif value == "any":
                weaker[label] = pos
            else:
                defined.add(label)
        pos += 1
    dropped_weaker = {
        label: position for label, position in weaker.items() if label in defined
    }
    kept = [part for i, part in enumerate(parts) if i not in dropped_weaker.values()]
    return ", ".join(kept)


class ConstType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"const"}

    @staticmethod
    def cddl(schema):
        return CONSTS.get(schema["const"])


class NumberType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "number" and {
            "type",
            "minimum",
            "maximum",
        }.issuperset(schema.keys())

    @staticmethod
    def cddl(schema):
        assert "maximum" not in schema
        if "minimum" not in schema:
            return "float"

        if schema.get("minimum") >= 0:
            return f"float .ge {schema['minimum']}"


class IntegerType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "integer" and {
            "type",
            "minimum",
            "maximum",
        }.issuperset(schema.keys())

    @staticmethod
    def cddl(schema):
        assert "minimum" in schema
        assert "maximum" not in schema
        if schema.get("minimum") >= 0:
            if schema.get("minimum") == 0:
                return "uint"
            else:
                return f"uint .ge {schema['minimum']}"
        else:
            return "int"


class ArrayType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "array" and {
            "type",
            "items",
            "minItems",
            "description",
        }.issuperset(schema.keys())

    @staticmethod
    def cddl(schema):
        type_class = find_type(schema["items"])
        if type_class is None:
            raise NotImplementedError(
                f"Unsupported array item schema: {schema['items']}"
            )
        item_cddl = type_class.cddl(schema["items"])
        if schema.get("minItems", 0) == 0:
            return f"[ * {item_cddl} ]"
        else:
            return f"[ + {item_cddl} ]"


class BooleanType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "boolean"

    @staticmethod
    def cddl(schema):
        return "bool"


class AnyOfType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"anyOf"}

    @staticmethod
    def cddl(schema):
        parts = []
        for subschema in schema["anyOf"]:
            type_class = find_type(subschema)
            if type_class is None:
                raise NotImplementedError(
                    f"Unsupported subschema in anyOf: {subschema}"
                )
            else:
                parts.append(type_class.cddl(subschema))
        return " / ".join(parts)


class IfThenElseType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"if", "then", "else"}

    @staticmethod
    def cddl(schema):
        parts = []
        type_class = find_type(schema["if"])
        if type_class is None:
            raise NotImplementedError(f"Unsupported subschema in if: {schema['if']}")
        parts.append(type_class.cddl(schema["if"], unwrap=True))
        type_class = find_type(schema["then"])
        if type_class is None:
            raise NotImplementedError(
                f"Unsupported subschema in then: {schema['then']}"
            )
        parts.append(type_class.cddl(schema["then"], unwrap=True))
        else_schema = schema["else"]
        if else_schema:
            assert schema["else"].keys() == {"const"}
            assert schema["else"]["const"].startswith("Not a")
        return f"{{ {drop_weaker_constraints(', '.join(parts))} }}"


class EnumType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"enum"}

    @staticmethod
    def cddl(schema):
        parts = []
        for enum_value in schema["enum"]:
            if isinstance(enum_value, str):
                parts.append(CONSTS.get(enum_value))
            else:
                parts.append(str(enum_value))
        return " / ".join(parts)


class NotConstType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"not"} and ConstType.is_one(schema["not"])

    @staticmethod
    def cddl(schema, unwrap=False):
        # Not directly representable in CDDL, this is only used in the extension_Extension
        # type, which is defined as any IRI, except the value "extension_Extension"
        return ""


class RefType:
    @staticmethod
    def is_one(schema):
        return (
            schema.keys() == {"$ref"}
            or schema.keys() == {"$ref", "type", "unevaluatedProperties"}
            and schema.get("type") == "object"
        )

    @staticmethod
    def cddl(schema, unwrap=False):
        defs, ref_name = schema["$ref"].rsplit("/", 1)
        assert defs == "#/$defs"
        return f"~{ref_name}" if unwrap else ref_name


class AllOfType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"allOf"}

    @staticmethod
    def cddl(schema, unwrap=False):
        parts = []
        for subschema in schema["allOf"]:
            type_class = find_type(subschema)
            if type_class is None:
                raise NotImplementedError(
                    f"Unsupported subschema in allOf: {subschema}"
                )
            parts.append(type_class.cddl(subschema, unwrap=True))
        inner = ", ".join(parts)
        return inner if unwrap else f"{{ {inner} }}"


class ObjectType:
    @staticmethod
    def is_one(schema):
        return (
            schema.get("type") == "object"
            and {
                "type",
                "unevaluatedProperties",
                "anyOf",
                "required",
                "properties",
            }.issuperset(schema.keys())
            and sum(["properties" in schema, "anyOf" in schema]) <= 1
        )

    @staticmethod
    def cddl(schema, unwrap=False):
        if "anyOf" in schema:
            return AnyOfType.cddl({"anyOf": schema["anyOf"]})
        if "properties" in schema:
            parts = []
            for prop_name, prop_schema in schema["properties"].items():
                type_class = find_type(prop_schema)
                if type_class is None:
                    raise NotImplementedError(
                        f"Unsupported property schema: {prop_schema}"
                    )
                optionality = "?" if prop_name not in schema.get("required", []) else ""
                interned_prop_name = LABELS.get(prop_name)
                parts.append(
                    f"{optionality}{interned_prop_name} => {type_class.cddl(prop_schema)}"
                )
            if not parts and schema.get("unevaluatedProperties", True):
                return "~AnyObject" if unwrap else "AnyObject"
            else:
                inner = ", ".join(parts)
                return inner if unwrap else f"{{ {inner} }}"

        if "required" in schema:
            parts = []
            for prop_name in schema["required"]:
                interned_prop_name = LABELS.get(prop_name)
                parts.append(f"{interned_prop_name} => any")
            inner = ", ".join(parts)
            return inner if unwrap else f"{{ {inner} }}"

        raise NotImplementedError(f"Unsupported object schema: {schema}")


class IfThenElseObjectType:
    @staticmethod
    def is_one(schema):
        return (
            schema.get("type") == "object"
            and {
                "type",
                "unevaluatedProperties",
                "required",
                "properties",
                "if",
                "then",
                "else",
            }.issuperset(schema.keys())
            and {"if", "then", "else"}.issubset(schema.keys())
        )

    @staticmethod
    def cddl(schema):
        first_part = []
        if_class = find_type(schema["if"])
        if if_class is None:
            raise NotImplementedError(f"Unsupported subschema in if: {schema['if']}")
        first_part.append(if_class.cddl(schema["if"], unwrap=True))
        then_class = find_type(schema["then"])
        if then_class is None:
            raise NotImplementedError(
                f"Unsupported subschema in then: {schema['then']}"
            )
        first_part.append(then_class.cddl(schema["then"], unwrap=True))
        second_part = []
        else_class = find_type(schema["else"])
        if else_class is None:
            raise NotImplementedError(
                f"Unsupported subschema in else: {schema['else']}"
            )
        second_part.append(else_class.cddl(schema["else"], unwrap=True))

        return f"{{ {drop_weaker_constraints(', '.join(first_part))} }} / {{ {drop_weaker_constraints(', '.join(second_part))} }}"


def find_type(schema):
    for type_class in [
        StringType,
        NumberType,
        IntegerType,
        AnyOfType,
        EnumType,
        BooleanType,
        RefType,
        ConstType,
        ObjectType,
        AllOfType,
        ArrayType,
        IfThenElseType,
        NotConstType,
        IfThenElseObjectType,
    ]:
        if type_class.is_one(schema):
            return type_class
    return None


class Grouping:
    # Only additional profiles, anything else goes into "Core"
    _PROFILES_NAMES = [
        "Software",
        "Security",
        "Licensing",
        "SimpleLicensing",
        "ExpandedLicensing",
        "Dataset",
        "AI",
        "Build",
        "Lite",
        "Extension",
    ]

    profiles = {}

    def __init__(self, defs):
        self.defs = defs
        self.profile_map = {}
        for profile_name in self._PROFILES_NAMES:
            self.profile_map[profile_name.lower()] = profile_name
            self.profile_map[f"prop_{profile_name.lower()}"] = profile_name
            self.profiles[profile_name] = []

        self.profiles["Core"] = []

        for name, schema in defs.items():
            core = True
            for key in self.profile_map.keys():
                if name.startswith(key):
                    self.profiles[self.profile_map[key]].append((name, schema))
                    core = False
            if core:
                self.profiles["Core"].append((name, schema))

    def to_profile(self, lower):
        return self.profile_map[lower]


DATETIME_TYPES = {
    "prop_CreationInfo_created",
    "prop_Relationship_endTime",
    "prop_Relationship_startTime",
    "prop_security_VulnAssessmentRelationship_security_modifiedTime",
    "prop_security_VulnAssessmentRelationship_security_publishedTime",
    "prop_security_VulnAssessmentRelationship_security_withdrawnTime",
    "prop_build_Build_build_buildEndTime",
    "prop_build_Build_build_buildStartTime",
    "prop_Artifact_builtTime",
    "prop_Artifact_releaseTime",
    "prop_Artifact_validUntilTime",
    "prop_security_Vulnerability_security_modifiedTime",
    "prop_security_Vulnerability_security_publishedTime",
    "prop_security_Vulnerability_security_withdrawnTime",
    "prop_security_VexAffectedVulnAssessmentRelationship_security_actionStatementTime",
    "prop_security_VexNotAffectedVulnAssessmentRelationship_security_impactStatementTime",
}

QUANTITY_TYPES = {
    "prop_security_CvssV2VulnAssessmentRelationship_security_score",
    "prop_security_CvssV3VulnAssessmentRelationship_security_score",
    "prop_security_CvssV4VulnAssessmentRelationship_security_score",
    "prop_security_EpssVulnAssessmentRelationship_security_percentile",
    "prop_security_EpssVulnAssessmentRelationship_security_probability",
    "prop_ai_EnergyConsumptionDescription_ai_energyQuantity",
}

DIGESTVALUE_TYPES = {"prop_Hash_hashValue"}
EXTENSIBLE_TYPES = {"AnyClass"}
CONTENT_TYPES = {
    "prop_software_File_contentType",
    "prop_ExternalRef_contentType",
    "prop_Annotation_contentType",
}
SEMVER_TYPES = {
    "prop_simplelicensing_LicenseExpression_simplelicensing_licenseListVersion",
    "prop_CreationInfo_specVersion",
}

if __name__ == "__main__":
    # Default to checked-in 3.0.1 schema if no path is provided
    schema_path = pathlib.Path(__file__).parent / "spdx-json-schema.json"
    if len(sys.argv) == 2:
        schema_path = pathlib.Path(sys.argv[1])
    schema = json.loads(schema_path.read_text())
    unmapped = []
    toplevel = {key: value for key, value in schema.items() if not key.startswith("$")}
    print(
        "; https://raw.githubusercontent.com/achamayou/draft-chamayou-cospdx/refs/heads/main/cospdx.cddl"
    )
    print("; Entry Point")
    print(declaration("SPDX_Document", toplevel, find_type(toplevel)))
    print()

    grouping = Grouping(schema["$defs"])

    for profile_name, definitions in grouping.profiles.items():
        if definitions:
            # Not all profiles define types
            print(f"; {profile_name} Profile")
            print()
            for type_name, type_schema in definitions:
                type_class = find_type(type_schema)
                if type_class is None:
                    unmapped.append((type_name, type_schema))
                else:
                    # Special casing, either for canonicality or for future extensibility
                    if type_name in DIGESTVALUE_TYPES:
                        print(
                            f"{type_name}_wrapped = #6.108(bstr) ; Strings in SPDX-JSON, usually hex-encoded"
                        )
                        print(f"{type_name} = ~{type_name}_wrapped")
                    elif type_name in DATETIME_TYPES:
                        print(
                            f"{type_name} = #6.1(uint) ; ISO8601 UTC with second-precision strings in SPDX-JSON"
                        )
                    elif type_name in EXTENSIBLE_TYPES:
                        print(
                            f"{type_name} = ${type_name} ; Socket for eventual post-SPDX 3.0.1 extensions"
                        )
                        values = type_class.cddl(type_schema).split(" / ")
                        for value in values:
                            print(f"${type_name} /= {value}")
                    elif type_name == "SHACLClass":
                        print(
                            f"{type_name} = {{ label.type => $label.type }} ; Socket for eventual post-SPDX 3.0.1 extensions"
                        )
                        label_type_values = (
                            type_class.cddl(type_schema)
                            .split(" => ")[1]
                            .split("}")[0]
                            .split(" / ")
                        )
                        for value in label_type_values:
                            print(f"$label.type /= {value}")
                    elif type_name in QUANTITY_TYPES:
                        # SPDX allows either float, or strings matching "^-?[0-9]+(\\.[0-9]*)?$"
                        # CoSPDX must make a choice for canonicality, and chooses the string representation
                        # because it avoids precision issues if the document is converted to SPDX JSON.
                        # The regexp is converted to its CDDL/XSD equivalent (https://www.rfc-editor.org/rfc/rfc8610#section-3.8.3)
                        print(
                            f'{type_name} = tstr .regexp "-?[0-9]+(\\\\.[0-9]*)?" ; CoSPDX representation of quantities'
                        )
                    elif type_name == "BlankNode":
                        # SPDX JSON pattern is "^_:.+", but CDDL regexp are matches, and we assume that the intention is not
                        # to match any line returns.
                        print(
                            f'{type_name} = tstr .regexp "_:.+" ; CoSPDX representation of blank nodes'
                        )
                    elif type_name in CONTENT_TYPES:
                        # SPDX JSON pattern is "^[^\\/]+\\/[^\\/]+$", but CDDL regexp are matches and the double escaping is not needed.
                        print(
                            f'{type_name} = tstr .regexp "[^/]+/[^/]+" ; CoSPDX representation of content types'
                        )
                    elif type_name == "IRI":
                        # SPDX JSON pattern is "^(?!_:).+:.+", but CDDL regexp are matches and do not support lookaheads.
                        # See fuzz_iri_regex.py for testing the equivalence of the patterns.
                        print(
                            f'{type_name} = tstr .regexp "[^_].*:.+|_[^:].*:.+" ; CoSPDX representation of IRIs'
                        )
                    elif type_name in SEMVER_TYPES:
                        # SPDX JSON pattern to match SemVer, but CDDL regexp are matches and do not support lookaheads.
                        # See fuzz_semver_regex.py for testing the equivalence of the patterns.
                        print(
                            f'{type_name} = tstr .regexp "(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\\+([0-9a-zA-Z-]+(\\.[0-9a-zA-Z-]+)*))?" ; CoSPDX representation of versions'
                        )
                    else:
                        print(declaration(type_name, type_schema, type_class))
            print()

    print("AnyObject = { * any => any }")
    print()
    print(f"; {LABELS.description()}")
    print(LABELS.definitions(grouping))
    print()
    print(f"; {CONSTS.description()}")
    print(CONSTS.definitions())

    unmapped_and_totalrefs = sorted(
        [
            (type_name, type_schema, totalrefs(type_name, schema["$defs"]))
            for type_name, type_schema in unmapped
        ],
        reverse=True,
        key=lambda x: x[2],
    )
    assert not unmapped_and_totalrefs, unmapped_and_totalrefs
