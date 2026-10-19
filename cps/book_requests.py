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

# Book requests: users ask for books that are not in the library (app.db tables book_request and
# book_request_vote). Every logged-in user can request and vote; an admin sets the status.

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, url_for, abort, jsonify
from flask_babel import gettext as _
from sqlalchemy import func

from .cw_login import current_user
from . import calibre_db, db, logger, ub
from .render_template import render_title_template
from .usermanagement import user_login_required

log = logger.create()

book_requests = Blueprint('book_requests', __name__)

BookRequest = ub.BookRequest
OPEN_STATES = (BookRequest.STATUS_OPEN, BookRequest.STATUS_LOOKING)
TABS = ('open', 'fulfilled', 'declined', 'mine')
MAX_TITLE, MAX_TEXT = 200, 500


def _tab_filter(query, tab):
    if tab == 'open':
        return query.filter(BookRequest.status.in_(OPEN_STATES))
    if tab == 'mine':
        return query.filter(BookRequest.votes.any(ub.BookRequestVote.user_id == current_user.id))
    return query.filter(BookRequest.status == tab)


def matching_books(title, limit=5):
    """Library books whose title contains the text, or the reverse, for duplicate hints and fulfilment."""
    title = (title or '').strip()
    if len(title) < 3:
        return []
    return calibre_db.session.query(db.Books).filter(calibre_db.common_filters()) \
        .filter(func.lower(db.Books.title).contains(title.lower())).order_by(db.Books.title).limit(limit).all()


def matching_requests(title):
    title = (title or '').strip()
    if len(title) < 3:
        return []
    return ub.session.query(BookRequest).filter(BookRequest.status.in_(OPEN_STATES)) \
        .filter(func.lower(BookRequest.title).contains(title.lower())).all()


def wants(book_request):
    return any(v.user_id == current_user.id for v in book_request.votes)


def unseen_updates():
    """Votes of the current user on requests that were fulfilled or declined since the user last looked."""
    if current_user.is_anonymous:
        return []
    return ub.session.query(ub.BookRequestVote).join(BookRequest) \
        .filter(ub.BookRequestVote.user_id == current_user.id, ub.BookRequestVote.seen == False,
                BookRequest.status.in_((BookRequest.STATUS_FULFILLED, BookRequest.STATUS_DECLINED))).all()


def navbar_context():
    """Numbers for the sidebar entry and the navbar bell, for every page (see render_title_template)."""
    if current_user.is_anonymous:
        return {}
    return dict(requests_open=ub.session.query(BookRequest).filter(BookRequest.status.in_(OPEN_STATES)).count(),
                requests_news=len(unseen_updates()))


def fulfilled_request(book_id):
    """The request that brought this book into the library, for the book page."""
    return ub.session.query(BookRequest).filter(BookRequest.book_id == book_id,
                                                BookRequest.status == BookRequest.STATUS_FULFILLED).first()


def _back(book_request=None):
    tab = request.form.get('tab') if request.form.get('tab') in TABS else 'open'
    return redirect(url_for('book_requests.list_requests', tab=tab) +
                    ('#request-{}'.format(book_request.id) if book_request else ''))


def _get(request_id):
    book_request = ub.session.query(BookRequest).filter(BookRequest.id == request_id).first()
    if not book_request:
        abort(404)
    return book_request


@book_requests.route("/requests")
@user_login_required
def list_requests():
    tab = request.args.get('tab', 'open')
    if tab not in TABS:
        tab = 'open'
    counts = {t: _tab_filter(ub.session.query(BookRequest), t).count() for t in TABS}
    rows = _tab_filter(ub.session.query(BookRequest), tab).all()
    rows.sort(key=lambda r: (-len(r.votes), -r.created.timestamp()))
    news = unseen_updates()
    news_requests = [v.request for v in news]
    for vote in news:
        vote.seen = True
    if news:
        ub.session_commit()
    book_ids = {r.book_id for r in rows + news_requests if r.book_id}
    books = {b.id: b for b in calibre_db.session.query(db.Books).filter(db.Books.id.in_(book_ids))
             .filter(calibre_db.common_filters()).all()} if book_ids else {}
    candidates = {r.id: matching_books(r.title) for r in rows if r.is_open} if current_user.role_admin() else {}
    return render_title_template('book_requests.html', rows=rows, tab=tab, counts=counts, news=news_requests,
                                 books=books, candidates=candidates, wants=wants,
                                 title=_("Book requests"), page="requests")


@book_requests.route("/requests/check")
@user_login_required
def check_request():
    title = request.args.get('title', '')
    return jsonify(
        library=[{'id': b.id, 'title': b.title, 'author': ' & '.join(a.name.replace('|', ',') for a in b.authors),
                  'url': url_for('web.show_book', book_id=b.id)} for b in matching_books(title)],
        requests=[{'id': r.id, 'title': r.title, 'votes': len(r.votes), 'wanted': wants(r),
                   'by': r.votes[0].user.name if r.votes and r.votes[0].user else '',
                   'vote_url': url_for('book_requests.vote', request_id=r.id)} for r in matching_requests(title)])


@book_requests.route("/requests/new", methods=["POST"])
@user_login_required
def new_request():
    title = (request.form.get('title') or '').strip()
    author = (request.form.get('author') or '').strip()
    note = (request.form.get('note') or '').strip()
    if not title:
        flash(_("A request needs a title."), category="error")
        return _back()
    if len(title) > MAX_TITLE or len(author) > MAX_TEXT or len(note) > MAX_TEXT:
        flash(_("The title, author or note is too long."), category="error")
        return _back()
    existing = ub.session.query(BookRequest).filter(BookRequest.status.in_(OPEN_STATES)) \
        .filter(func.lower(BookRequest.title) == title.lower()).first()
    if existing:
        if not wants(existing):
            existing.votes.append(ub.BookRequestVote(user_id=current_user.id))
            ub.session_commit("User {} voted for book request {}".format(current_user.id, existing.id))
        flash(_("Somebody already requested '%(title)s'. Your vote is added to that request.", title=existing.title),
              category="info")
        return _back(existing)
    book_request = BookRequest(title=title, author=author, note=note)
    book_request.votes.append(ub.BookRequestVote(user_id=current_user.id))
    ub.session.add(book_request)
    ub.session_commit("User {} requested book '{}'".format(current_user.id, title))
    flash(_("Your request for '%(title)s' is added.", title=title), category="success")
    return _back(book_request)


@book_requests.route("/requests/<int:request_id>/vote", methods=["POST"])
@user_login_required
def vote(request_id):
    book_request = _get(request_id)
    mine = [v for v in book_request.votes if v.user_id == current_user.id]
    if mine:
        book_request.votes.remove(mine[0])
        if not book_request.votes:
            ub.session.delete(book_request)
            ub.session_commit("Book request {} removed, no votes left".format(request_id))
            flash(_("Your request for '%(title)s' is withdrawn.", title=book_request.title), category="info")
            return _back()
    elif book_request.is_open:
        book_request.votes.append(ub.BookRequestVote(user_id=current_user.id))
    else:
        abort(400)
    ub.session_commit("User {} changed vote on book request {}".format(current_user.id, request_id))
    return _back(book_request)


@book_requests.route("/requests/<int:request_id>/status", methods=["POST"])
@user_login_required
def set_status(request_id):
    if not current_user.role_admin():
        abort(403)
    book_request = _get(request_id)
    action = request.form.get('action')
    if action == 'delete':
        ub.session.delete(book_request)
        ub.session_commit("Admin {} deleted book request {}".format(current_user.id, request_id))
        return _back()
    if action == 'looking' and book_request.is_open:
        book_request.status = BookRequest.STATUS_LOOKING
    elif action == 'fulfil' and book_request.is_open:
        book_id = request.form.get('book_id', type=int) or request.form.get('book_id_other', type=int)
        if not book_id or not calibre_db.get_filtered_book(book_id):
            flash(_("Pick a book from the library to fulfil the request."), category="error")
            return _back(book_request)
        book_request.status, book_request.book_id, book_request.reason = BookRequest.STATUS_FULFILLED, book_id, ""
    elif action == 'decline' and book_request.is_open:
        reason = (request.form.get('reason') or '').strip()[:MAX_TEXT]
        if not reason:
            flash(_("Give a reason, so the people who want the book know why."), category="error")
            return _back(book_request)
        book_request.status, book_request.book_id, book_request.reason = BookRequest.STATUS_DECLINED, None, reason
    elif action == 'reopen' and not book_request.is_open:
        book_request.status, book_request.book_id, book_request.reason = BookRequest.STATUS_OPEN, None, ""
    else:
        abort(400)
    book_request.done_by = current_user.id
    book_request.done_at = datetime.now(timezone.utc)
    for v in book_request.votes:
        v.seen = v.user_id == current_user.id
    ub.session_commit("Admin {} set book request {} to {}".format(current_user.id, request_id, book_request.status))
    return _back(book_request)
