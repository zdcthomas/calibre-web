/* global $ */
// Bulk upload: send each file in its own request, show a row per file, keep going when one fails.

$(function () {
    var form = $("#form-upload");
    if (!form.length) {
        return;
    }
    var LIMIT = 2; // ponytail: parallel uploads fixed at 2, make it a setting if servers choke
    var queue = [], active = 0, done = 0, failed = 0, total = 0, uploaded = [];

    var modal = $('<div class="modal fade" id="bulk-upload-modal" data-backdrop="static" data-keyboard="false">' +
        '<div class="modal-dialog modal-lg"><div class="modal-content">' +
        '<div class="modal-header"><h4 class="modal-title"></h4></div>' +
        '<div class="modal-body" style="max-height:60vh;overflow-y:auto"><table class="table table-condensed" id="bulk-upload-rows"></table></div>' +
        '<div class="modal-footer"><span class="pull-left text-muted" id="bulk-upload-summary"></span>' +
        '<span class="pull-left text-muted" id="bulk-upload-next" style="display:none;margin-left:1em"></span>' +
        '<button type="button" class="btn btn-default" id="bulk-upload-close" disabled></button></div>' +
        "</div></div></div>").appendTo("body");
    modal.find(".modal-title").text(form.data("title"));
    $("#bulk-upload-next").text(form.data("next"));
    $("#bulk-upload-close").text(form.data("footer")).click(function () {
        // hand the new books to the bulk edit panel, so shelves and metadata can be set in one go
        if (uploaded.length) {
            var selection = {};
            try {
                selection = JSON.parse(sessionStorage.getItem("bulk-selection")) || {};
            } catch (e) { /* start fresh */ }
            uploaded.forEach(function (id) { selection[id] = true; });
            try {
                sessionStorage.setItem("bulk-selection", JSON.stringify(selection));
            } catch (e) { /* no storage, no selection */ }
        }
        location.reload(); // flashes, sidebar counts and the new books all need a fresh page
    });

    function esc(text) {
        return $("<span>").text(text).html();
    }

    function summary() {
        $("#bulk-upload-summary").text(form.data("summary")
            .replace("{done}", done).replace("{total}", total).replace("{failed}", failed));
        $("#bulk-upload-close").prop("disabled", done < total);
        $("#bulk-upload-next").toggle(done >= total && uploaded.length > 0);
    }

    function setStatus(item, kind, html) {
        item.tr.find(".progress-bar").attr("class", "progress-bar progress-bar-" + kind).css("width", "100%");
        item.tr.find(".bulk-upload-status").html(html);
    }

    function finish(item, xhr) {
        var res = null;
        try {
            res = JSON.parse(xhr.responseText);
        } catch (e) { /* not json */ }
        // some flashes carry server-rendered HTML; keep only their text (DOMParser runs no scripts)
        var messages = ((res && res.messages) || []).map(function (m) {
            return esc(new DOMParser().parseFromString(m, "text/html").body.textContent.replace(/\s+/g, " ").trim());
        }).join("<br>");
        active--;
        done++;
        if (res && res.success) {
            uploaded.push(res.book_id);
            setStatus(item, "success", '<a href="' + res.location + '">' + esc(res.title) + "</a>" +
                (messages ? "<br>" + messages : ""));
        } else if (res && res.duplicate) {
            failed++;
            setStatus(item, "warning", esc(form.data("duplicate")) + ' <a href="' + res.location + '">' +
                esc(res.title) + '</a> &middot; <a href="#" class="bulk-upload-anyway">' + esc(form.data("anyway")) + "</a>");
            item.tr.find(".bulk-upload-anyway").click(function (e) {
                e.preventDefault();
                done--;
                failed--;
                item.tr.find(".progress-bar").attr("class", "progress-bar").css("width", "0%");
                item.tr.find(".bulk-upload-status").empty();
                send(item, true);
            });
        } else {
            failed++;
            setStatus(item, "danger", messages ||
                (xhr.status === 0 ? esc(form.data("network")) : esc(form.data("failed")) + " " + xhr.status));
        }
        summary();
        next();
    }

    function send(item, allowDuplicate) {
        active++;
        var data = new FormData();
        data.append("csrf_token", form.find("input[name=csrf_token]").val());
        data.append("batch", "1");
        if (allowDuplicate) {
            data.append("allow_duplicate", "1");
        }
        data.append("btn-upload", item.file, item.file.name);
        var xhr = new XMLHttpRequest();
        xhr.open("POST", form.attr("action"));
        xhr.setRequestHeader("X-REQUESTED-WITH", "XMLHttpRequest");
        xhr.upload.addEventListener("progress", function (e) {
            if (e.lengthComputable) {
                item.tr.find(".progress-bar").css("width", Math.round(e.loaded / e.total * 100) + "%");
            }
        });
        xhr.addEventListener("load", function () { finish(item, xhr); });
        xhr.addEventListener("error", function () { finish(item, xhr); });
        xhr.send(data);
    }

    function next() {
        while (active < LIMIT && queue.length) {
            send(queue.shift(), false);
        }
    }

    form.on("submit", function (e) {
        e.preventDefault();
        var files = $("#btn-upload")[0].files;
        if (!files.length) {
            return;
        }
        $("#bulk-upload-rows").empty();
        queue = [];
        uploaded = [];
        active = done = failed = 0;
        total = files.length;
        $.each(files, function (i, file) {
            var tr = $('<tr><td class="bulk-upload-name"></td><td style="width:35%"><div class="progress">' +
                '<div class="progress-bar" style="width:0%"></div></div></td><td class="bulk-upload-status small"></td></tr>');
            tr.find(".bulk-upload-name").text(file.name);
            $("#bulk-upload-rows").append(tr);
            queue.push({file: file, tr: tr});
        });
        summary();
        modal.modal("show");
        next();
    });
});
