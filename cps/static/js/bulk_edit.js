/* global $, getPath */
// Bulk edit panel: select covers, then add/remove shelves or set metadata for all selected books.

$(function () {
    var panel = $("#bulk-panel");
    if (!panel.length) {
        return;
    }
    var selection = {};
    try {
        selection = JSON.parse(sessionStorage.getItem("bulk-selection")) || {};
    } catch (e) {
        selection = {};
    }

    function ids() {
        return Object.keys(selection).map(Number);
    }

    function post(url, data) {
        return $.ajax({
            method: "post",
            contentType: "application/json; charset=utf-8",
            dataType: "json",
            url: getPath() + url,
            data: JSON.stringify(data)
        });
    }

    function flash(kind, msg) {
        $("#flash_success, #flash_danger").parent().remove();
        $(".navbar").after('<div class="row-fluid text-center"><div id="flash_' + kind +
            '" class="alert alert-' + kind + '">' + msg + "</div></div>");
    }

    function fail(xhr) {
        var res = xhr.responseJSON || {};
        flash("danger", res.msg || xhr.statusText);
    }

    function render() {
        var count = ids().length;
        try {
            sessionStorage.setItem("bulk-selection", JSON.stringify(selection));
        } catch (e) { /* ignore */ }
        $(".bulk-check").each(function () {
            var on = !!selection[$(this).data("bookId")];
            $(this).closest(".book").toggleClass("bulk-selected", on).attr("draggable", on);
        });
        $("#bulk-count").text(count);
        panel.toggleClass("hidden", count === 0);
        $("body").toggleClass("bulk-open", count > 0);
        if (count === 0) {
            return;
        }
        post("/ajax/shelf/membership", {selections: ids()}).done(function (counts) {
            $(".bulk-shelf").each(function () {
                var on = counts[$(this).data("shelfId")] || 0;
                $(this).attr("data-state", on === 0 ? "none" : on === count ? "all" : "some")
                    .find(".bulk-state").text(on + "/" + count);
            });
        });
    }

    function shelfAction(action, shelfId) {
        post("/ajax/shelf/" + action + "/" + shelfId, {selections: ids()}).done(function (res) {
            flash("success", res.msg);
            // the shelf page itself lists the books, so refresh it after a removal
            if (action === "remove" && /\/shelf\/\d+/.test(location.pathname)) {
                location.reload();
            } else {
                render();
            }
        }).fail(fail);
    }

    $(document).on("click", ".bulk-check", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var id = $(this).data("bookId");
        if (selection[id]) {
            delete selection[id];
        } else {
            selection[id] = true;
        }
        render();
    });

    $("#bulk-clear").click(function (e) {
        e.preventDefault();
        selection = {};
        render();
    });

    $(document).on("click", ".bulk-shelf", function () {
        shelfAction($(this).attr("data-state") === "all" ? "remove" : "add", $(this).data("shelfId"));
    });

    $(document).on("click", ".bulk-set", function () {
        var input = $(this).closest(".bulk-field").find("input");
        var value = input.val().trim();
        if (!value) {
            return;
        }
        var data = {selections: ids(), checkA: true, checkT: true};
        data[input.data("field")] = value;
        post("/ajax/editselectedbooks", data).done(function (res) {
            var errors = (res || []).filter(function (item) { return item.success !== true; });
            if (errors.length) {
                flash("danger", errors.map(function (item) { return item.msg; }).join("<br>"));
            } else {
                location.reload(); // the cards show the old values until the page renders again
            }
        }).fail(fail);
    });

    // drag any selected cover onto a sidebar shelf
    var shelfLinks = $("#scnd-nav a[href*='/shelf/']").filter(function () {
        return /\/shelf\/\d+$/.test($(this).attr("href"));
    });
    $(document).on("dragstart", ".book.bulk-selected", function (e) {
        e.originalEvent.dataTransfer.setData("text", "bulk-selection");
    });
    shelfLinks.on("dragover", function (e) {
        e.preventDefault();
        $(this).parent().addClass("bulk-droptarget");
    }).on("dragleave drop", function () {
        $(this).parent().removeClass("bulk-droptarget");
    }).on("drop", function (e) {
        e.preventDefault();
        shelfAction("add", $(this).attr("href").match(/\/shelf\/(\d+)$/)[1]);
    });

    render();
});
