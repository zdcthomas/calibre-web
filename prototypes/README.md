# Comments prototype (throwaway)

`comments-variants.html` is a standalone mock of the book detail page and the
shelf page with three comment designs, switchable with `?variant=A|B|C` or the
yellow bar. The bar also switches between the book page and the shelf page,
and between the users zach (admin), maria and tom. Open it with any static
file server, for example `python3 -m http.server --directory prototypes`.

Question it answers: what should user comments on books and on shelves look
like in Calibre-Web, and how do shelf comments relate to the books on the shelf?

- **A, thread under the details.** A "Discussion" section under the book
  description and under the shelf grid. One level of replies. A shelf comment
  can be "about" one book; the book page then lists it under "Mentioned in
  shelf discussions". A deleted comment that has replies stays as a placeholder.
- **B, side drawer.** A "Comments (n)" button opens a right-hand drawer with a
  flat list (Quote instead of Reply). Shelf covers show a count badge. The shelf
  drawer has two tabs: comments on the shelf, and comments on its books.
- **C, activity feed.** The shelf page is a timeline that mixes shelf comments,
  comments on its books, and shelf events (book added or removed). One composer
  posts to the shelf or to one book. The book page has an activity rail.

These are user discussion threads (author, time, text). They are not Calibre's
"comments" column, which is the book description. Real storage would be a new
table in `app.db` (`cps/ub.py`), never in `metadata.db`.

Verdict: pending.

This branch is the primary source for that decision. Nothing here ships.
