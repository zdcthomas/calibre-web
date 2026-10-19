# Book requests prototype (throwaway)

`book-requests-variants.html` is a standalone mock of Calibre-Web with three
designs for book requests, switchable with `?variant=A|B|C` or the yellow bar.
The bar also switches between the users zach (admin), maria and tom. Open it
with any static file server, for example
`python3 -m http.server --directory prototypes`.

Question it answers: how do users ask for books that are not in the library,
how does everyone see who wants what, and how does a request end?

Shared model in all variants:

- A request has a title, an optional author and an optional note.
- People "want" a request. The first person is the requester. Withdraw means
  remove your vote; a request that nobody wants goes away.
- Status: requested, looking for it, in the library (linked to a library
  book), declined (with a reason). An admin changes the status.
- When you type a title, the form shows matching library books and matching
  open requests, so you add a vote instead of a duplicate.
- A bell in the navbar tells every person who wanted a book when it arrives
  or when it is declined.

Variants:

- **A, Requests page.** A sidebar entry opens a list sorted by votes, with a
  request form on top, tabs per status, and admin actions on each row.
- **B, Board.** Columns per status. The admin drags cards between columns;
  a drop on "In the library" asks for the book, a drop on "Declined" asks for
  a reason.
- **C, In the library.** "Wanted" ghost covers above the Books grid. A search
  with no result offers "Request it". The admin uploads a file straight into a
  request, and the new book shows a "Requested by" ribbon.

Real storage would be new tables in `app.db` (`cps/ub.py`).

Verdict: pending.

This branch is the primary source for that decision. Nothing here ships.
