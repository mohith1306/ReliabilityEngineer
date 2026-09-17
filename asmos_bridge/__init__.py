"""Bridge onto the ASMOS mechanism -- verification-gated ownership routing.

Derived from the ASMOS research project (C:/Users/csdee/PESU/CDSAML/ASMOS,
installable package `asmos`). See docs/architecture/ASMOS_INTEGRATION.md for the
mapping and ADR-0001 for why this is a vendored bridge rather than a dependency.

NOT named `asmos/`: the real package imports as `asmos`, and a local top-level
package of that name shadows it silently.

These are ASMOS's equations. Every module names the upstream file it derives from.
ASMOS's published numbers are ASMOS results and are cited as such.
"""
