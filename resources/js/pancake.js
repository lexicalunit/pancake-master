/* global $, _, Spinner */
/* exported build_market, by_location, film_times */

var api_base = 'https://feeds.drafthouse.com/adcService/showtimes.svc/market'
var search_terms = []
var status_number = 0
var storage = $.initNamespaceStorage('pancake').sessionStorage

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
}
var spinner = new Spinner(spiner_opts)

// Parse any query parameters.
var query_parameters = {}
;(window.onpopstate = function () {
  var match
  var pl = /\+/g // Regex for replacing addition symbol with a space
  var search = /([^&=]+)=?([^&]*)/g
  var decode = function (s) {
    return decodeURIComponent(s.replace(pl, ' '))
  }
  var query = window.location.search.substring(1)
  while ((match = search.exec(query))) {
    query_parameters[decode(match[1])] = decode(match[2])
  }
})()

// Default to searching for Master Pancake shows, then consider query parameter
// if it has been provided, and finally override with any search input.
function init_query () {
  window.search_terms = ['pancake']
  if ('q' in query_parameters) {
    // query = query_parameters['q']
    if (!$('#q').val()) {
      $('#q').val(query_parameters['q'])
    }
  }
  var terms = $('#q').val().split(/[\s,]+/)
  if (terms.length && terms[0].length) {
    window.search_terms = terms
  }
}

function capwords (text) {
  return text.replace(/\w\S*/g, function (txt) {
    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
  })
}

function pad (num, size) {
  var s = num + ''
  while (s.length < size) {
    s = '0' + s
  }
  return s
}

function status (text) {
  status_number++
  var li = document.createElement('li')
  li.className = 'status_item'
  li.id = 'status_' + status_number
  li.innerHTML = text
  $('#statuses').append(li)
  return status_number
}

function status_update (text, number) {
  $('#status_' + number).html(text)
}

function search () {
  $('#main').empty()
  init_query()
  var films = storage.isSet('films') ? storage.get('films') : []
  var matching_films = []
  for (var i = 0; i < films.length; i++) {
    var film = films[i]
    if (matches_search(film.title)) {
      matching_films.push(film)
    }
  }
  build_films(matching_films)
}

function matches_search (title) {
  for (var i = 0; i < search_terms.length; i++) {
    var re = new RegExp(search_terms[i], 'i')
    if (title.match(re)) {
      return true
    }
  }
  return false
}

function build_films (films) {
  var template = _.template($('script.template').html())
  $('#main').html(template(films))
  $('h1').fitText(1.5)
  $('h2').fitText(3)
}

function slugify (text) {
  return text.toLowerCase().replace(/[^\w ]+/g, '').replace(/ +/g, '-')
}

function parse_market (data) {
  var shows = []
  if (data.hasOwnProperty('error')) {
    status('error: ' + data.error)
    storage.set('films', shows)
    spinner.stop()
    search()
    return
  }
  var status_message = 'Parsing Market Data...'
  var status_id = status(status_message)
  for (var d = 0; d < data.Market.Dates.length; d++) {
    var date = data.Market.Dates[d]
    var film_date = date.Date
    for (var c = 0; c < date.Cinemas.length; c++) {
      var cinema = date.Cinemas[c]
      var cinema_id = cinema.CinemaId
      var cinema_name = 'Alamo Drafthouse ' + cinema.CinemaName
      var cinema_url = 'https://drafthouse.com/theater/' + slugify(cinema.CinemaName)
      for (var f = 0; f < cinema.Films.length; f++) {
        var film = cinema.Films[f]
        var film_uid = film.FilmId
        var film_name = film.FilmName
        for (var s = 0; s < film.Series.length; s++) {
          var series = film.Series[s]
          for (var m = 0; m < series.Formats.length; m++) {
            var format = series.Formats[m]
            for (var n = 0; n < format.Sessions.length; n++) {
              var session = format.Sessions[n]
              var session_id = session.SessionId
              var film_url = 'https://drafthouse.com/ticketing/' + cinema_id + '/' + session_id
              var show = {
                title: capwords(film_name.toLowerCase()),
                film_uid: film_uid,
                cinema: cinema_name,
                cinema_url: cinema_url,
                date: film_date,
                time: session.SessionTime,
                status: session.SessionStatus,
                url: session.SessionStatus === 'onsale' ? film_url : null
              }
              shows.push(show)
            }
          }
        }
      }
    }
  }
  status_update(status_message + ' done.', status_id)
  storage.set('films', shows)
  spinner.stop()
  search()
}

function initialize_page () {
  $('#main').empty()
  $('#statuses').empty()
  init_query()
  spinner.spin(document.getElementById('spin'))
  status_number = 0
}

function initialize_storage () {
  if (storage.isSet('films')) return false
  storage.set('films', [])
  return true
}

function build_market () {
  initialize_page()
  var did_initialize_storage = initialize_storage()
  if (!did_initialize_storage) {
    status('Data fetched from session storage.')
    spinner.stop()
    search()
    return
  }
  var status_message = 'Fetching Market Data...'
  var status_id = status(status_message)
  var marketid = pad(0, 4)
  $.when($.ajax({
    url: api_base + '/' + marketid,
    success: parse_market,
    error: function (jqXHR, status, error) {
      // status_update(status_message + "failed: " + status + ": " + error)
    }
  })).then(function (data, status, jqXHR) {
    status_update(status_message + ' done.', status_id)
  })
}

function by_location (films) {
  return _.groupBy(films, function (film) {
    return [film.title, film.cinema]
  })
}

function film_time (film) {
  var span = document.createElement('span')
  span.className = film.status
  if (film.status === 'onsale') {
    var a = document.createElement('a')
    a.href = film.url
    a.innerHTML = film.time
    span.innerHTML = a.outerHTML
  } else {
    span.innerHTML = film.time
  }
  return span.outerHTML
}

function film_times (films) {
  return films.map(function (film) {
    return film_time(film)
  })
}

_.templateSettings.variable = 'rc'
