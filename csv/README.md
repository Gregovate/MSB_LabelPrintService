# Runtime CSV Exports

LabelPrintService writes transient batch exports into this directory at runtime.
The files are operational output, not source or test fixtures, and are ignored by
Git so a successful print batch does not leave the deployed checkout dirty.

Current configured outputs include:

```text
display_labels.csv
container_labels_vertical.csv
container_labels_horizontal.csv
controller_labels.csv
```

Do not place durable test fixtures here. Tracked sample/fixture CSV files belong
with the responsible printer template under `templates/<printer>/csv/`.

Before removing or replacing a runtime CSV during incident recovery, inspect the
corresponding execution batch and logs. A CSV may be useful evidence when a
physical-print boundary is uncertain even though it is not committed to Git.
