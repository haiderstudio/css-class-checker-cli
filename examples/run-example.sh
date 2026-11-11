#!/bin/sh
# Run the checker on the bundled example site and show the report.
# The checker exits 1 because the example stylesheet has unused
# classes; that is the point of the examples, so this script exits 0.
cd "$(dirname "$0")/.." || exit 2
python3 src/css_class_checker.py examples/site || true
