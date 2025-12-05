#!/usr/bin/env python3

import json
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


class ConstType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"const"}

    @staticmethod
    def cddl(schema):
        return f"\"{schema['const']}\""


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
        # TODO: can we handle maximum / minimum better?
        if schema.get("minimum") == 0:
            return "uint / float"
        else:
            return "int / float"


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
        # TODO: can we handle maximum / minimum better?
        if schema.get("minimum") == 0:
            return "uint"
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
        return f"{{ {', '.join(parts)} }}"


class EnumType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"enum"}

    @staticmethod
    def cddl(schema):
        parts = []
        # TODO: Systematic mapping to integers
        for enum_value in schema["enum"]:
            if isinstance(enum_value, str):
                parts.append(f'"{enum_value}"')
            else:
                parts.append(str(enum_value))
        return " / ".join(parts)


class NotConstType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"not"} and ConstType.is_one(schema["not"])

    @staticmethod
    def cddl(schema, unwrap=False):
        return ""
        # TODO: add back once line returns are added
        # return f"; must not be {ConstType.cddl(schema['not'])}"


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
            # TODO: Allocate integer property keys for compactness
            for prop_name, prop_schema in schema["properties"].items():
                type_class = find_type(prop_schema)
                if type_class is None:
                    raise NotImplementedError(
                        f"Unsupported property schema: {prop_schema}"
                    )
                optionality = "?" if prop_name not in schema.get("required", []) else ""
                parts.append(
                    f'{optionality}"{prop_name}": {type_class.cddl(prop_schema)}'
                )
            if not parts and schema.get("unevaluatedProperties", True):
                return "~AnyObject" if unwrap else "AnyObject"
            else:
                inner = ", ".join(parts)
                return inner if unwrap else f"{{ {inner} }}"

        if "required" in schema:
            parts = []
            for prop_name in schema["required"]:
                parts.append(f'"{prop_name}": any')
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

        return f"{{ {', '.join(first_part)} }} / {{ {', '.join(second_part)} }}"


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
        profile_map = {}
        for profile_name in self._PROFILES_NAMES:
            profile_map[profile_name.lower()] = profile_name
            profile_map[f"prop_{profile_name.lower()}"] = profile_name
            self.profiles[profile_name] = []

        self.profiles["Core"] = []

        for name, schema in defs.items():
            core = True
            for key in profile_map.keys():
                if name.startswith(key):
                    self.profiles[profile_map[key]].append((name, schema))
                    core = False
            if core:
                self.profiles["Core"].append((name, schema))


if __name__ == "__main__":
    # Default to checked-in 3.0.1 schema if no path is provided
    input_path = pathlib.Path(__file__).parent / "spdx-json-schema.json"
    if len(sys.argv) == 2:
        input_path = pathlib.Path(sys.argv[1])
    schema = json.loads(input_path.read_text())
    unmapped = []
    toplevel = {key: value for key, value in schema.items() if not key.startswith("$")}
    # TODO: Tag entry point? Link CDDL as context?
    print("; " + "=" * 80)
    print("; Entry Point")
    print(declaration("SPDX_Document", toplevel, find_type(toplevel)))
    print("; " + "=" * 80)
    print()

    grouping = Grouping(schema["$defs"])

    for profile_name, definitions in grouping.profiles.items():
        if definitions:
            # Not all profiles define types
            print("; " + "=" * 80)
            print(f"; {profile_name} Profile")
            print("; " + "=" * 80)
            print()
            for type_name, type_schema in definitions:
                type_class = find_type(type_schema)
                if type_class is None:
                    unmapped.append((type_name, type_schema))
                else:
                    print(declaration(type_name, type_schema, type_class))
            print("; " + "=" * 80)
            print()
            print()

    print("AnyObject = { * any => any }")

    unmapped_and_totalrefs = sorted(
        [
            (type_name, type_schema, totalrefs(type_name, schema["$defs"]))
            for type_name, type_schema in unmapped
        ],
        reverse=True,
        key=lambda x: x[2],
    )
    assert not unmapped_and_totalrefs, unmapped_and_totalrefs
