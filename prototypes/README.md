# Bulk edit prototype (throwaway)

`bulk-edit-variants.html` is a standalone mock of the Books page with three
bulk-edit designs, switchable with `?variant=A|B|C` or the yellow bar.
Open it with any static file server, for example `python3 -m http.server`.

Question it answered: what should bulk metadata edit and bulk shelf moves
look like in Calibre-Web?

Verdict (2026-10-19): **B** wins. A persistent right-hand panel, click a cover
to select, tri-state shelf rows that apply at once, per-field metadata rows,
and drag the selected covers onto a sidebar shelf. A and C are dropped.

This branch is the primary source for that decision. Nothing here ships.
