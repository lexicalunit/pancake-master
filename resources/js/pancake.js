var api_base = "https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/";
var films = [];
var matching_films = [];
var n_found_cinemas = 0;
var n_parsed_cinemas = 0;
var search_terms = [];
var status_number = 0;

// Spinner to indicate Alamo Drafthouse data is being fetched/processed.
var spiner_opts = {
    lines: 13, // The number of lines to draw
    length: 20, // The length of each line
    width: 10, // The line thickness
    radius: 30, // The radius of the inner circle
    corners: 1, // Corner roundness (0..1)
    rotate: 0, // The rotation offset
    direction: 1, // 1: clockwise, -1: counterclockwise
    color: '#FFF', // #rgb or #rrggbb or array of colors
    speed: 1, // Rounds per second
    trail: 60, // Afterglow percentage
    shadow: false, // Whether to render a shadow
    hwaccel: false, // Whether to use hardware acceleration
    className: 'spinner', // The CSS class to assign to the spinner
    zIndex: 2e9, // The z-index (defaults to 2000000000)
    top: '50%', // Top position relative to parent
    left: '50%' // Left position relative to parent
};
var spinner = new Spinner(window.spiner_opts);

// Parse any query parameters.
var params = {};
(window.onpopstate = function () {
    var match,
        pl     = /\+/g,  // Regex for replacing addition symbol with a space
        search = /([^&=]+)=?([^&]*)/g,
        decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
        query  = window.location.search.substring(1);
    while (match = search.exec(query))
        window.params[decode(match[1])] = decode(match[2]);
})();

// Default to searching for Master Pancake shows, then consider query parameter
// if it has been provided, and finally override with any search input.
function init_query() {
    window.search_terms = ["pancake"];
    if("q" in window.params) {
        query = window.params["q"];
        if(!$("#q").val()) {
            $("#q").val(window.params["q"]);
        }
    }
    var terms = $("#q").val().split(/[\s,]+/);
    if(terms.length && terms[0].length) {
        window.search_terms = terms;
    }
}

function capwords(text) {
    return text.replace(/\w\S*/g, function(txt) {
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
}

function pad(num, size) {
    var s = num + "";
    while (s.length < size)
        s = "0" + s;
    return s;
}

function daystr() {
    var today = new Date();
    var dd = pad(today.getDate(), 2);
    var mm = pad(today.getMonth() + 1, 2);
    var yyyy = today.getFullYear();
    return yyyy + mm + dd;
}

function status(text) {
    window.status_number++;
    var li = document.createElement('li');
    li.className = "status_item";
    li.id = "status_" + window.status_number;
    li.innerHTML = text;
    $("#statuses").append(li);
    return window.status_number;
}

function status_update(text, number) {
    $("#status_" + number).html(text);
}

function search() {
    $("#main").empty();
    init_query();
    window.matching_films = [];
    for(var i =0; i < window.films.length; i++) {
        var film = window.films[i];
        if(matches_search(film.title)) {
            window.matching_films.push(film);
        }
    }
    build_films();
}

function matches_search(title) {
    for(var i = 0; i < window.search_terms.length; i++) {
        var re = new RegExp(window.search_terms[i], 'i');
        if(title.match(re)) {
            return true;
        }
    }
    return false;
}

function build_films() {
    var template = _.template($("script.template").html());
    $("#main").html(template(window.matching_films));
    $("h1").fitText(1.5);
    $("h2").fitText(3);
}

function parse_cinema(data) {
    var status_message = "Parsing " + data.Cinema.CinemaName + " Data...";
    var status_id = status(status_message);
    for(var i = 0; i < data.Cinema.Dates.length; i++) {
        var date_data = data.Cinema.Dates[i];
        for(var j = 0; j < date_data.Films.length; j++) {
            var film_data = date_data.Films[j];
            for(var k = 0; k < film_data.Sessions.length; k++) {
                var session_data = film_data.Sessions[k];
                film = {
                    // film: capwords(film_data.Film.replace("Master Pancake: ", "").toLowerCase())
                    title: capwords(film_data.Film.toLowerCase())
                    , film_uid: film_data.FilmId
                    , cinema: data.Cinema.CinemaName
                    , cinema_url: data.Cinema.CinemaURL
                    , date: date_data.Date
                    , time: session_data.SessionTime
                    , status: session_data.SessionStatus
                    , url: session_data.SessionStatus == "onsale" ? session_data.SessionSalesURL : null
                };
                window.films.push(film);
            }
        }
    }
    status_update(status_message + " done.", status_id);
}

function build_cinema(cinema) {
    var status_message = "Fetching " + cinema.CinemaName + " Data...";
    var status_id = status(status_message);
    $.when($.ajax({
        url: window.api_base + "CinemaSessions.aspx"
        , dataType: "jsonp"
        , jsonp: "callback"
        , data: {
            cinemaid: pad(cinema.CinemaId, 4)
        }
        , success: parse_cinema
    })).then(function(data, textStatus, jqXHR) {
        status_update(status_message + " done.", status_id);
        window.n_parsed_cinemas++;
        if(window.n_parsed_cinemas == window.n_found_cinemas) {
            window.spinner.stop();
            search();
        }
    });
}

function build_cinemas(cinemas) {
    var status_message = "Parsing Cinemas Data...";
    var status_id = status(status_message);
    for(var i = 0; i < cinemas.length; i++) {
        var cinema = cinemas[i];
        build_cinema(cinema);
    }
    status_update(status_message + " done.", status_id);
}

function parse_market(data) {
    var status_message = "Parsing Market Data...";
    var status_id = status(status_message);
    var cinemas = [];
    for(var i = 0; i < data.Market.Cinemas.length; i++) {
        var cinema = data.Market.Cinemas[i];
        if(cinema.CinemaId == '0090') {
            continue;
        }
        var item = {
            CinemaId: cinema.CinemaId
            , CinemaName: cinema.CinemaName
            , CinemaURL: cinema.CinemaURL
        };
        cinemas.push(item);
    }
    window.n_found_cinemas = cinemas.length;
    status_update(status_message + " done.", status_id);
    build_cinemas(cinemas);
}

function build_market() {
    $("#main").empty();
    $("#statuses").empty();
    init_query();
    window.spinner.spin(document.getElementById('spin'));
    window.status_number = 0;

    var status_message = "Fetching Market Data...";
    var status_id = status(status_message);
    $.when($.ajax({
        url: window.api_base + "marketsessions.aspx"
        , dataType: "jsonp"
        , jsonp: "callback"
        , data: {
            date: daystr()
            , marketid: pad(0, 4)
        }
        , success: parse_market
    })).then(function(data, textStatus, jqXHR) {
        status_update(status_message + " done.", status_id);
    });
}

function by_location(films) {
    return _.groupBy(films, function(film) {
        return [film.title, film.cinema];
    });
}

function film_time(film) {
    var span = document.createElement('span');
    span.className = film.status;
    if(film.status == "onsale") {
        var a = document.createElement('a');
        a.href = film.url;
        a.innerHTML = film.time;
        span.innerHTML = a.outerHTML;
    } else {
        span.innerHTML = film.time;
    }
    return span.outerHTML;
}

function film_times(films) {
    return films.map(function(film) {
        return film_time(film);
    });
}

_.templateSettings.variable = "rc";
