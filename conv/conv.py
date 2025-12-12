#!/usr/bin/env python3

"""
TODO:

- Convert datetimes to epoch integers
- Experiment with id compression
"""

import json
import sys
import pathlib
import cbor2


class Schema:
    labels = {}
    enums = {}
    consts = {}

    def __init__(self, schema_path: pathlib.Path):
        for line in schema_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("label."):
                label, value = line[len("label.") :].split("=")
                self.labels[label.strip()] = int(value.strip())
            elif line.startswith("enum."):
                enum, value = line[len("enum.") :].split("=")
                self.enums[enum.strip()] = int(value.strip())
            elif line.startswith("const."):
                const, value = line[len("const.") :].split("=")
                self.consts[const.strip()] = value.strip()
        assert self.consts.keys().isdisjoint(self.enums.keys()), (
            self.consts.keys() & self.enums.keys()
        )


def simple_value_convert(key, value, schema):
    if key == "hashValue":
        return bytes.fromhex(value)
    if isinstance(value, str):
        if value in schema.consts:
            return schema.consts[value]
        elif value in schema.enums:
            return schema.enums[value]
    return value


def mapped(document, schema):
    map = {}
    for key, value in document.items():
        val = value
        if isinstance(value, dict):
            val = mapped(value, schema)
        elif isinstance(value, list):
            val = [
                mapped(item, schema) if isinstance(item, dict) else item
                for item in value
            ]
        map[schema.labels.get(key, key)] = simple_value_convert(key, val, schema)
    return map


def convert(document_path, schema_path):
    document = json.loads(document_path.read_text())
    schema = Schema(schema_path)
    return cbor2.dumps(mapped(document, schema))


if __name__ == "__main__":
    if len(sys.argv) == 4:
        input_path = pathlib.Path(sys.argv[1])
        output_path = pathlib.Path(sys.argv[2])
        schema_path = pathlib.Path(sys.argv[3])
    else:
        print("Usage: conv.py <spdx3.json> <output.cbor> <schema.cddl>")
        sys.exit(1)
    with output_path.open("wb") as fd:
        fd.write(convert(input_path, schema_path))
