#!/usr/bin/env python3

import json
from re import S
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

    def __init__(self, name, schema):
        assert StringType.is_one(schema)
        assert {"type", "pattern", "allOf"}.issuperset(schema.keys()), schema.keys()
        self.name = name
        self.schema = schema

    def to_cddl(self):
        if "pattern" in self.schema:
            pattern = self.schema["pattern"]
            return f'{self.name} = tstr .regexp "{pattern}"'

        if "allOf" in self.schema:
            patterns = []
            for value in self.schema["allOf"]:
                assert value.keys() == {"pattern"}
                patterns.append(f'tstr .regexp "{value["pattern"]}"')
            return f'{self.name} = {" / ".join(patterns)}'

        return f"{self.name} = tstr"


class NumberType:
    @staticmethod
    def is_one(schema):
        return schema.get("type") == "number"

    def __init__(self, name, schema):
        assert NumberType.is_one(schema)
        assert {"type", "minimum", "maximum"}.issuperset(schema.keys()), schema.keys()
        self.name = name
        self.schema = schema

    def to_cddl(self):
        if self.schema.get("mininum") == 0:
            parts = [self.name + " = uint"]
        else:
            parts = [self.name + " = int"]
        return " ".join(parts)


def find_type(schema):
    for type_class in [StringType, NumberType]:
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

    print("\n# Unmapped types with no reference:")
    for type_name in unmapped:
        print(f"# - {type_name}")
