#!/usr/bin/env python3

import json
from re import S
import re
import sys
import pathlib
from tarfile import SUPPORTED_TYPES


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

    def __init__(self, name, schema):
        assert StringType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {StringType.cddl(self.schema)}"


class ConstType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"const"}

    @staticmethod
    def cddl(schema):
        return f"\"{schema['const']}\""

    def __init__(self, name, schema):
        assert ConstType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {ConstType.cddl(self.schema)}"


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

    def __init__(self, name, schema):
        assert NumberType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {NumberType.cddl(self.schema)}"


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

    def __init__(self, name, schema):
        assert IntegerType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {IntegerType.cddl(self.schema)}"


class BooleanType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "boolean"

    @staticmethod
    def cddl(schema):
        return "bool"

    def __init__(self, name, schema):
        assert BooleanType.is_one(schema)
        assert {"type"}.issuperset(schema.keys()), schema.keys()
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {BooleanType.cddl(self.schema)}"


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

    def __init__(self, name, schema):
        assert AnyOfType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {AnyOfType.cddl(self.schema)}"


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

    def __init__(self, name, schema):
        assert EnumType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {EnumType.cddl(self.schema)}"


class RefType:
    @staticmethod
    def is_one(schema):
        return schema.keys() == {"$ref"}

    @staticmethod
    def cddl(schema):
        defs, ref_name = schema["$ref"].rsplit("/", 1)
        assert defs == "#/$defs"
        return ref_name

    def __init__(self, name, schema):
        assert RefType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {RefType.cddl(self.schema)}"


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
            and (schema.get("properties") is None or schema.get("anyOf") is None)
        )

    @staticmethod
    def cddl(schema):
        # TODO: when unevaluatedProperties is true (not set), we should allow additional properties
        if "anyOf" in schema:
            return AnyOfType.cddl({"anyOf": schema["anyOf"]})
        # TODO: handle required properties
        if "properties" in schema:
            parts = []
            # TODO: Allocate integer property keys for compactness
            for prop_name, prop_schema in schema["properties"].items():
                type_class = find_type(prop_schema)
                if type_class is None:
                    raise NotImplementedError(
                        f"Unsupported property schema: {prop_schema}"
                    )
                parts.append(f'"{prop_name}": {type_class.cddl(prop_schema)}')
            return f"{{ {', '.join(parts)} }}"

        raise NotImplementedError(f"Unsupported object schema: {schema}")

    def __init__(self, name, schema):
        assert ObjectType.is_one(schema)
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {ObjectType.cddl(self.schema)}"


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
        AnyOfType,
        ObjectType,
    ]:
        if type_class.is_one(schema):
            return type_class
    return None


if __name__ == "__main__":
    # Default to checked-in 3.0.1 schema if no path is provided
    input_path = pathlib.Path(__file__).parent / "spdx-json-schema.json"
    if len(sys.argv) == 2:
        input_path = pathlib.Path(sys.argv[1])
    schema = json.loads(input_path.read_text())
    stats(schema)
    unmapped = []
    for type_name, type_schema in schema["$defs"].items():
        type_class = find_type(type_schema)
        if type_class is None:
            unmapped.append((type_name, type_schema))
        else:
            # try:
            type_instance = type_class(type_name, type_schema)
            print(type_instance.to_cddl())
            # except NotImplementedError as e:
            #     unmapped.append(type_name)

    print()
    print(f"; Unmapped types: {len(unmapped)}")
    unmapped_and_totalrefs = sorted(
        [
            (type_name, type_schema, totalrefs(type_name, schema["$defs"]))
            for type_name, type_schema in unmapped
        ],
        reverse=True,
        key=lambda x: x[2],
    )
    for type_name, type_schema, total_refs in unmapped_and_totalrefs:
        print(f"; - {type_name}: {total_refs} refs")
