"""Reliability lifecycle engines.

Owns the incident lifecycle: investigate -> diagnose -> assess risk -> approve ->
remediate -> verify -> learn. Does NOT do software engineering; that is Bob's job
(see `bob/`). See docs/ARCHITECTURE.md section 4.1 and its corrections in
docs/architecture/ERRATA.md.
"""
