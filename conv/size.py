#!/usr/bin/env python3

from conv import convert
import os
import pathlib

if __name__ == "__main__":
    samples_dir = pathlib.Path("samples")
    schema_path = pathlib.Path("../cospdx.cddl")

    for root, dirs, files in os.walk(samples_dir):
        for file in files:
            if file.endswith(".json"):
                file_path = pathlib.Path(root) / file
                try:
                    converted = convert(file_path, schema_path)
                    converted_with_string_refs = convert(
                        file_path, schema_path, string_referencing=True
                    )
                    file_size = file_path.stat().st_size
                    converted_size = len(converted)
                    converted_size_with_string_refs = len(converted_with_string_refs)
                    print(
                        f"{str(file_path):<64}: JSON: {str(file_size):<8} CBOR: {str(converted_size):<8}  Ratio: {converted_size / file_size:.2f} CBOR (string refs): {str(converted_size_with_string_refs):<8}  Ratio: {converted_size_with_string_refs / file_size:.2f}"
                    )
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
