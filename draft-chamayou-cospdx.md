---
title: "A Deterministic Compact (CBOR) Encoding for SPDX"
abbrev: "Deterministic Compact SPDX"
category: std

docname: draft-chamayou-cospdx
submissiontype: IETF
number:
date:
consensus: true
v: 3
area: Security
workgroup: CBOR
keyword:
 - CBOR
 - SPDX
 - deterministic
venue:
  group: CBOR
  type: Working Group
  mail: cbor@ietf.org
  arch: [https://example.com/WG](https://www.ietf.org/mail-archive/web/cbor/current/maillist.html)
  github: achamayou/draft-chamayou-cospdx

author:
 -
    fullname: Amaury Chamayou
    organization: Microsoft
    email: amchamay@microsoft.com

normative:

informative:

...

--- abstract

This document proposes a canonical serialization of SPDX 3.0.1 to CBOR, to enable the reproducible and efficient creation of System Package Data Exchange information. This representation is consistent with, and lends itself to being used with transparency services proposed by the Supply Chain Integrity, Transparency and Trust initiative.

--- middle

# Introduction

The System Package Data Exchange specification defines an open start for communicating bill of materials information for different topic areas, and multiple serialization formats to encode that data model.

Defined serialization formats for SPDX 3.0.1 are text-based and so tend to produce large payloads even for documents that describe a relatively small number of artifacts. A JSON canonical serialisation, using RFC8259, is defined in SPDX 3.0.1, but is unevenly available because not many JSON libraries implement RFC8259.

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
