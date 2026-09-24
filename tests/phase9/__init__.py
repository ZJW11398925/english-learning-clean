"""Phase 9 tests — the trust-boundary and carryover cut (P9-0).

This package is P9-0's own slice suite. Its four modules map one-to-one onto
the cut's four rulings: the §14 ``factor_trace`` document (A), the Gate's
``ContinuationFacts.terminalizing_action`` (B), the untrusted prompt framing
(门三 / C), and the ``ReviewEvent`` writer contract with its anchor referral
(D).

The **world** is borrowed deliberately, the way phase 8 borrowed phase 7's:
the P8-0 cycle fixtures and the P8-4 world builder are the shipped chain, and
re-spelling them here would be a second copy of a wired world. What is *not*
borrowed is any assertion: every claim this package makes is its own.
"""
