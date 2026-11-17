"""Renders the Khandhakas (Kd 1–22) as a folder of interlinked markdown notes.

Each Khandhaka gets a folder containing:
  - a "0 - <Chapter name>.md" summary and table of contents,
  - a note for every heading, which is an index if it has several notes
    under it, and
  - a note for each "unit" of the text (see `splitting`).

How a chapter becomes notes, in the order it happens:
  sections  - the headings in the source html become a tree
  atoms     - the text under a heading is cut up at every place it could be split
  splitting - the pieces which belong together are put back together
  planning  - the headings and units are numbered and named as notes
  rendering - the text of a note is rendered as markdown
  pages     - and gets its links to the notes around it
  generator - then it's all written to disk

Everything but `generator` is pure functions of the text.

See https://github.com/obu-labs/pali-vinaya-notes/issues/7
"""
