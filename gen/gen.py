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


def types_with_no_refs(schema):
    return {name: node for name, node in schema["$defs"].items() if refs(node) == 0}


def stats(schema):
    print(f"# {len(schema['$defs'])} definitions")
    print(f"# {refs(schema)} references")
    types_with_no_refs_count = len(types_with_no_refs(schema))
    print(f"# {types_with_no_refs_count} types with no references")
    print()


class StringType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "string"

    @staticmethod
    def cddl(schema):
        if "pattern" in schema:
            pattern = schema["pattern"]
            return f'tstr .regexp "{pattern}"'

        if "allOf" in schema:
            patterns = []
            for value in schema["allOf"]:
                assert value.keys() == {"pattern"}
                patterns.append(f'tstr .regexp "{value["pattern"]}"')
            return {" / ".join(patterns)}

        return "tstr"

    def __init__(self, name, schema):
        assert StringType.is_one(schema)
        assert {"type", "pattern", "allOf"}.issuperset(schema.keys()), schema.keys()
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {StringType.cddl(self.schema)}"


class NumberType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "number"

    @staticmethod
    def cddl(schema):
        # TODO: can we handle maximum / minimum better?
        if schema.get("minimum") == 0:
            return "uint / float"
        else:
            return "int / float"

    def __init__(self, name, schema):
        assert NumberType.is_one(schema)
        assert {"type", "minimum", "maximum"}.issuperset(schema.keys()), schema.keys()
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {NumberType.cddl(self.schema)}"


class IntegerType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "integer"

    @staticmethod
    def cddl(schema):
        # TODO: can we handle maximum / minimum better?
        if schema.get("minimum") == 0:
            return "uint"
        else:
            return "int"

    def __init__(self, name, schema):
        assert IntegerType.is_one(schema)
        assert {"type", "minimum", "maximum"}.issuperset(schema.keys()), schema.keys()
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
        return "anyOf" in schema

    @staticmethod
    def cddl(schema):
        parts = []
        for subschema in schema["anyOf"]:
            type_class = find_type(subschema)
            if type_class is None:
                raise NotImplementedError(
                    f"Unsupported subschema in anyOf: {subschema}"
                )
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
        return "enum" in schema

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
        assert {"enum"}.issuperset(schema.keys()), schema.keys()
        self.name = name
        self.schema = schema

    def to_cddl(self):
        return f"{self.name} = {EnumType.cddl(self.schema)}"


def find_type(schema):
    for type_class in [
        StringType,
        NumberType,
        IntegerType,
        AnyOfType,
        EnumType,
        BooleanType,
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
    for type_name, type_schema in types_with_no_refs(schema).items():
        type_class = find_type(type_schema)
        if type_class is None:
            unmapped.append(type_name)
        else:
            type_instance = type_class(type_name, type_schema)
            print(type_instance.to_cddl())

    print()
    print(f"# Unmapped types with no reference ({len(unmapped)}):")
    for type_name in unmapped:
        print(f"# - {type_name}")
    unmapped = 0
    for type_name, type_schema in schema["$defs"].items():
        if find_type(type_schema) is None:
            unmapped += 1
    print(f"# Unmapped types: {unmapped}")
