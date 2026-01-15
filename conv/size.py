#!/usr/bin/env python3

from collections import defaultdict
from conv import convert
import os
import pathlib
import lzma
import subprocess

if __name__ == "__main__":
    samples_dir = pathlib.Path("samples")
    schema_path = pathlib.Path("../cospdx.cddl")

    sbom_tool = defaultdict(list)
    spdx_samples = defaultdict(list)

    for root, dirs, files in os.walk(samples_dir):
        for file in sorted(files):
            if file.endswith(".json") and not root.endswith("ccf"):
                file_path = pathlib.Path(root) / file
                try:
                    converted = convert(file_path, schema_path)
                    # converted_with_string_refs = convert(
                    #     file_path, schema_path, string_referencing=True
                    # )
                    file_size = file_path.stat().st_size
                    converted_size = len(converted)
                    # converted_size_with_string_refs = len(converted_with_string_refs)
                    spdx_json = file_path.read_text()
                    lzma_compressed = lzma.compress(spdx_json.encode())
                    lzma_size = len(lzma_compressed)
                    cbor_packed = subprocess.run(
                        ["json2cbor.rb", "-p", str(file_path)],
                        capture_output=True,
                    )
                    packed_size = len(cbor_packed.stdout)
                    print(
                        f"{str(file_path):<64}: JSON: {str(file_size):<8} CoSPDX: {str(converted_size):<8}  Ratio: {converted_size / file_size:.2f} Packed CoSPDX: {packed_size / file_size:.2f} LZMA: {lzma_size / file_size:.2f}"
                    )
                    if "sbom-tool" in root:
                        sbom_tool["CoSPDX Ratios"].append(converted_size / file_size)
                        sbom_tool["LZMA Ratios"].append(lzma_size / file_size)
                        sbom_tool["Packed CoSPDX Ratios"].append(packed_size / file_size)
                    else:
                        spdx_samples["CoSPDX Ratios"].append(converted_size / file_size)
                        spdx_samples["LZMA Ratios"].append(lzma_size / file_size)
                        spdx_samples["Packed CoSPDX Ratios"].append(packed_size / file_size)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
    
    print()
    print("SPDX Samples Averages:")
    for key, values in spdx_samples.items():
        average = sum(values) / len(values) if values else 0
        print(f"  {key}: {average:.2f}")
    print()
    print("SBOM-Tool Samples Averages:")
    for key, values in sbom_tool.items():
        average = sum(values) / len(values) if values else 0
        print(f"  {key}: {average:.2f}")
