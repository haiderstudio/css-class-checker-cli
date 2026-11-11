# Contributing

Small, focused improvements are welcome.

- Open an issue first for anything larger than a typo or a clearer example, so the scope can be agreed before work starts.
- Never weaken the safety rules: an unused class must stay a fail, and the tool must never rewrite a file. Do not turn this into a duplicate/similar-class checker — that job belongs to ruilisi/css-checker.
- Every claim in a proposed change must be verifiable: a command must be runnable, a pass or fail must be real, a badge must be true.
- Run `python3 tests/test_css_class_checker.py` before opening a pull request. It must pass.
- Do not add placeholder text, invented features, or copied content without attribution.
- Python standard library only — no new dependency without a reason in the issue.
