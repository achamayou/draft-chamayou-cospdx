---
title: "A Deterministic Compact (CBOR) Encoding for SPDX"
abbrev: "Deterministic Compact SPDX"
category: std

docname: draft-chamayou-cospdx-latest
submissiontype: IETF
number:
date:
consensus: true
v: 3
# area: Security
# workgroup: CBOR
keyword:
 - CBOR
 - SPDX
 - deterministic
venue:
#  group: CBOR
#  mail: cbor@ietf.org
  github: "achamayou/draft-chamayou-cospdx"

author:
-  name: Amaury Chamayou
   organization: Microsoft
   email: amchamay@microsoft.com

normative:
  SPDX:
    target: https://spdx.dev/use/specifications/
    title: SPDX Specification
  CBOR-LD:
    target: https://json-ld.github.io/cbor-ld-spec/
    title: CBOR-LD
  RFC8610:

informative:
  SER-SPDX:
    target: https://spdx.github.io/spdx-spec/v3.0.1/serializations
    title: Serialization for SPDX
  CAN-SPDX:
    target: https://spdx.github.io/spdx-spec/v3.0.1/serializations/#canonical-serialization
    title: Canonical Serialization for SPDX
  RFC8259:

...

--- abstract

This document proposes a canonical serialization of SPDX 3.0.1 to CBOR, to enable the reproducible and efficient creation of System Package Data Exchange information. This representation is consistent with, and lends itself to being used with transparency services proposed by the Supply Chain Integrity, Transparency and Trust initiative.

--- middle

# Introduction

The System Package Data Exchange ({{SPDX}}) specification defines an open standard for communicating bill of materials information for different topic areas, and multiple serialization formats to encode that data model.

Serialization formats defined for SPDX 3.0.1 (see {{SER-SPDX}}) are text-based and so tend to produce large payloads even for documents that describe a relatively small number of artifacts. A JSON canonical serialisation ({{CAN-SPDX}}), based on {{RFC8259}} with additional encoding rules, is defined in SPDX 3.0.1, but is not widely implemented by SBOM generation tools currently.

This document follows an approach similar to that proposed by {{CBOR-LD}}, but aims to contribute CDDL schemas ({{RFC8610}}) rather than registries for the various SPDX profiles that describe how to emit CBOR-encoded SPDX 3.0.1 directly.

# CDDL Schema

~~~ cddl
{::include_fold cospdx.cddl}
~~~

# Conventions and Definitions

{::boilerplate bcp14-tagged}


# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.


--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
