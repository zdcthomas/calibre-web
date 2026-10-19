# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

# User discussion threads on books and shelves (app.db table user_comment).
# Not the Calibre "comments" column, which holds the book description.

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, url_for, abort
from flask_babel import gettext as _
from sqlalchemy import or_

from .cw_login import current_user
from . import calibre_db, db, logger, ub
from .shelf import check_shelf_view_permissions
from .usermanagement import user_login_required

log = logger.create()

comments = Blueprint('comments', __name__)

MAX_COMMENT_LENGTH = 5000


def load_thread(book_id=None, shelf_id=None):
    """Return ([(top_level_comment, [replies])], live_comment_count), oldest first."""
    query = ub.session.query(ub.UserComment)
    if book_id is not None:
        query = query.filter(ub.UserComment.book_id == book_id)
    else:
        query = query.filter(ub.UserComment.shelf_id == shelf_id)
    rows = query.order_by(ub.UserComment.created, ub.UserComment.id).all()
    replies = {}
    for c in rows:
        if c.parent_id is not None:
            replies.setdefault(c.parent_id, []).append(c)
    thread = [(c, replies.get(c.id, [])) for c in rows if c.parent_id is None]
    return thread, sum(1 for c in rows if not c.deleted)


def shelf_mentions(book_id):
    """Shelf comments about this book, on shelves the current user can see."""
    query = ub.session.query(ub.UserComment, ub.Shelf).join(ub.Shelf, ub.Shelf.id == ub.UserComment.shelf_id) \
        .filter(ub.UserComment.about_book_id == book_id, ub.UserComment.deleted == False)
    if current_user.is_anonymous:
        query = query.filter(ub.Shelf.is_public == 1)
    else:
        query = query.filter(or_(ub.Shelf.is_public == 1, ub.Shelf.user_id == current_user.id))
    return query.order_by(ub.UserComment.created).all()


def book_titles(book_ids):
    """Titles of visible books, for the "about" chips on shelf comments."""
    book_ids = {b for b in book_ids if b}
    if not book_ids:
        return {}
    rows = calibre_db.session.query(db.Books.id, db.Books.title).filter(db.Books.id.in_(book_ids)) \
        .filter(calibre_db.common_filters(True)).all()
    return dict(rows)


def thread_context(book_id=None, shelf=None, shelf_books=()):
    """Template data for comment_thread.html, splatted into render_title_template."""
    thread, count = load_thread(book_id=book_id, shelf_id=shelf.id if shelf else None)
    ctx = dict(comment_thread=thread, comment_count=count,
               can_edit_comment=can_edit, can_delete_comment=can_delete)
    if shelf:
        ctx.update(comment_post_url=url_for('comments.add_shelf_comment', shelf_id=shelf.id),
                   comment_about_books=[(b.id, b.title) for b in shelf_books],
                   comment_about_titles=book_titles(c.about_book_id for c, __ in thread),
                   comment_private=not shelf.is_public)
    else:
        mentions = shelf_mentions(book_id)
        ctx.update(comment_post_url=url_for('comments.add_book_comment', book_id=book_id),
                   comment_mentions=mentions, comment_private=False)
    return ctx


def can_edit(comment):
    return not comment.deleted and not current_user.is_anonymous and comment.user_id == current_user.id


def can_delete(comment):
    return not comment.deleted and not current_user.is_anonymous and \
        (comment.user_id == current_user.id or current_user.role_admin())


def _target_url(comment, anchor=True):
    if comment.book_id is not None:
        url = url_for('web.show_book', book_id=comment.book_id)
    else:
        url = url_for('shelf.show_shelf', shelf_id=comment.shelf_id)
    return url + ('#comment-{}'.format(comment.id) if anchor and comment.id else '#comments')


def _target_visible(comment):
    if comment.book_id is not None:
        return calibre_db.get_filtered_book(comment.book_id, allow_show_archived=True) is not None
    shelf = ub.session.query(ub.Shelf).filter(ub.Shelf.id == comment.shelf_id).first()
    return shelf is not None and check_shelf_view_permissions(shelf)


def _read_text():
    text = (request.form.get('text') or '').strip()
    if not text:
        flash(_("A comment can not be empty."), category="error")
        return None
    if len(text) > MAX_COMMENT_LENGTH:
        flash(_("A comment can have a maximum of %(max)s characters.", max=MAX_COMMENT_LENGTH), category="error")
        return None
    return text


def _add(comment):
    text = _read_text()
    if text is None:
        return redirect(_target_url(comment, anchor=False))
    comment.text = text
    comment.user_id = current_user.id
    parent_id = request.form.get('parent_id', type=int)
    if parent_id:
        parent = ub.session.query(ub.UserComment).filter(ub.UserComment.id == parent_id).first()
        if not parent or parent.book_id != comment.book_id or parent.shelf_id != comment.shelf_id:
            abort(400)
        # One level of replies: a reply to a reply goes under the top-level comment.
        comment.parent_id = parent.parent_id or parent.id
    ub.session.add(comment)
    ub.session_commit("User {} added comment on {}".format(current_user.id,
                      "book {}".format(comment.book_id) if comment.book_id else "shelf {}".format(comment.shelf_id)))
    return redirect(_target_url(comment))


@comments.route("/comment/book/<int:book_id>", methods=["POST"])
@user_login_required
def add_book_comment(book_id):
    if not calibre_db.get_filtered_book(book_id, allow_show_archived=True):
        abort(404)
    return _add(ub.UserComment(book_id=book_id))


@comments.route("/comment/shelf/<int:shelf_id>", methods=["POST"])
@user_login_required
def add_shelf_comment(shelf_id):
    shelf = ub.session.query(ub.Shelf).filter(ub.Shelf.id == shelf_id).first()
    if not shelf or not check_shelf_view_permissions(shelf):
        abort(404)
    about = request.form.get('about_book_id', type=int)
    if about and not ub.session.query(ub.BookShelf).filter(ub.BookShelf.shelf == shelf_id,
                                                            ub.BookShelf.book_id == about).first():
        abort(400)
    return _add(ub.UserComment(shelf_id=shelf_id, about_book_id=about or None))


def _get_comment(comment_id):
    comment = ub.session.query(ub.UserComment).filter(ub.UserComment.id == comment_id).first()
    if not comment or not _target_visible(comment):
        abort(404)
    return comment


@comments.route("/comment/<int:comment_id>/edit", methods=["POST"])
@user_login_required
def edit_comment(comment_id):
    comment = _get_comment(comment_id)
    if not can_edit(comment):
        abort(403)
    text = _read_text()
    if text is not None and text != comment.text:
        comment.text = text
        comment.edited = datetime.now(timezone.utc)
        ub.session_commit("User {} edited comment {}".format(current_user.id, comment_id))
    return redirect(_target_url(comment))


@comments.route("/comment/<int:comment_id>/delete", methods=["POST"])
@user_login_required
def delete_comment(comment_id):
    comment = _get_comment(comment_id)
    if not can_delete(comment):
        abort(403)
    url = _target_url(comment, anchor=False)
    ub.delete_user_comment(comment)
    ub.session_commit("User {} deleted comment {}".format(current_user.id, comment_id))
    return redirect(url)
