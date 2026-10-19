/* Book requests page: while the user types a title, show matching library books and open requests. */
$(function () {
    var $title = $("#request-title"), $hints = $("#request-hints");
    if (!$title.length) { return; }
    var csrf = $("input[name='csrf_token']").first().val(), timer = null, last = "";
    function show(data) {
        $hints.empty();
        data.library.forEach(function (b) {
            $("<div class='request-hint-library'>").append(
                $("<span class='glyphicon glyphicon-ok'>"), " " + $hints.data("in-library") + " ",
                $("<a>").attr("href", b.url).text(b.title), b.author ? " (" + b.author + ")" : ""
            ).appendTo($hints);
        });
        data.requests.forEach(function (r) {
            var $row = $("<div class='request-hint-request'>").append(
                $("<span class='glyphicon glyphicon-warning-sign'>"), " ",
                String($hints.data("requested")).replace("{by}", r.by) + ": ", $("<strong>").text(r.title),
                " (" + String($hints.data("votes")).replace("{n}", r.votes) + ") ");
            if (r.wanted) {
                $row.append(document.createTextNode($hints.data("you-want")));
            } else {
                $("<form method='POST' style='display:inline'>").attr("action", r.vote_url).append(
                    $("<input type='hidden' name='csrf_token'>").val(csrf),
                    $("<button type='submit' class='btn btn-link btn-xs'>").text($hints.data("add-vote"))
                ).appendTo($row);
            }
            $row.appendTo($hints);
        });
    }
    $title.on("input", function () {
        clearTimeout(timer);
        var value = $.trim($title.val());
        if (value.length < 3) { $hints.empty(); last = ""; return; }
        timer = setTimeout(function () {
            if (value === last) { return; }
            last = value;
            $.getJSON($hints.data("check-url"), {title: value}).done(function (data) {
                if ($.trim($title.val()) === value) { show(data); }
            });
        }, 250);
    });
});
