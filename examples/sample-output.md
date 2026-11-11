# Sample output

Output of `sh examples/run-example.sh` — the checker run over
the whole `examples/site/` folder (2 CSS files, 13 classes,
4 problems in 1 file):

```
examples/site/clean.css: OK — all 2 class(es) used
FAIL examples/site/styles.css:18: unused class '.title' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:21: unused class '.unused-banner' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:24: unused class '.unused-footer' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:28: unused class '.sidebar' — not referenced in any HTML, JS, JSX, TS, or TSX file
Checked 2 CSS file(s) (13 class(es)), 4 problem(s) in 1 file(s).
```

The four unused classes are `.title` (defined in the `.card
.title` rule, but no page uses a `title` class), `.unused-banner`,
`.unused-footer`, and `.sidebar` (inside the media query, still
checked). The `.fake-class` named in the comment at the top of
`styles.css` is not reported — comments are never read as classes.
