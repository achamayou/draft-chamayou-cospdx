#!/usr/bin/env python3

from conv import convert
import os
import pathlib
import lzma

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
                    spdx_json = file_path.read_text()
                    lzma_compressed = lzma.compress(spdx_json.encode())
                    lzma_size = len(lzma_compressed)
                    print(
                        f"{str(file_path):<64}: JSON: {str(file_size):<8} CoSPDX: {str(converted_size):<8}  Ratio: {converted_size / file_size:.2f} CoSPDXsr: {converted_size_with_string_refs / file_size:.2f} LZMA: {lzma_size / file_size:.2f}"
                    )
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
