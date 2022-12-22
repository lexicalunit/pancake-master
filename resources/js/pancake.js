/* global $, _, Spinner */
/* exported build_market, by_location, film_times, show_all_titles */

window.markets = {}
var feed_api_url = 'https://feeds.drafthouse.com/adcService/showtimes.svc/market/'

// NOTE: There's an issue with CORS on iOS mobile web browsers, so I created a
//       CORS enabled AWS API that simply proxies the feed_api_url, above.
// TODO: Figure out if there's any way to resolve this issue without this workaround.
var proxy_api_url = 'https://vl9ijl59gk.execute-api.us-west-2.amazonaws.com/prod'
var use_proxy = false

var api_url
if (use_proxy) {
  api_url = proxy_api_url
} else {
  api_url = feed_api_url
}

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

const austin_market_id = '0000'
function selected_market () {
  const value = $('#m')[0].value
  if (value && value !== 'Austin') {
    return window.markets[value] || austin_market_id
  }
  return austin_market_id
}

// Default to searching for Master Pancake shows, then consider query parameter
// if it has been provided, and finally override with any search input.
function init_query () {
  window.search_terms = ['pancake']
  if ('q' in query_parameters) {
    if (!$('#q').val()) {
      $('#q').val(query_parameters['q'])
    }
  }
  var terms = $('#q').val().match(/\w+|"(?:\\"|[^"])+"/g)
  if (terms && terms.length && terms[0].length) {
    window.search_terms = terms
  }
}

function capwords (text) {
  return text.replace(/\w\S*/g, function (txt) {
    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
  })
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

function escape_reg_exp (str) {
  return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&')
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

function unquote (str) {
  var quote_char = '"'
  if (str[0] === quote_char && str[str.length - 1] === quote_char) {
    return str.slice(1, str.length - 1)
  } else return str
}

function matches_search (title) {
  for (var i = 0; i < search_terms.length; i++) {
    var re = new RegExp(unquote(search_terms[i]), 'i')
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

function parse_markets (response) {
  const { data } = response
  if (!data) return
  const { marketSummaries } = data
  if (!marketSummaries) return
  const marketNames = [];
  marketSummaries.forEach(summary => {
    marketNames.push(summary.name)
    window.markets[summary.name] = summary.id
  })
  $('#m').autocomplete({
    source: marketNames,
    minLength: 0,
    select: function (event, ui) {
      $('#m').val(ui.item.value)
      build_market()
      return false
    }
  })


}

function parse_market (data) {
  var shows = []
  if (data.hasOwnProperty('error')) {
    status('error: ' + data.error)
    storage.set('films', shows)
    spinner.stop()
    show_titles()
    search()
    return
  }
  var status_message = 'Parsing Market Data...'
  var status_id = status(status_message)
  var market_slug = data.Market.MarketSlug
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
        var film_slug = film.FilmSlug
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
                cinema_id: cinema_id,
                cinema_url: cinema_url,
                cinema: cinema_name,
                date: film_date,
                film_slug: film_slug,
                film_uid: film_uid,
                market_slug: market_slug,
                status: session.SessionStatus,
                time: session.SessionTime,
                title: capwords(film_name.toLowerCase()),
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
  show_titles()
  search()
}

function initialize_page () {
  $('#main').empty()
  $('#statuses').empty()
  init_query()
  spinner.spin(document.getElementById('spin'))
  status_number = 0
}

function initialize_storage (new_market) {
  if (storage.isSet('films') && !new_market) return false
  storage.set('films', [])
  return true
}

function show_titles () {
  var films = storage.isSet('films') ? storage.get('films') : []
  var titles = {}
  for (var i = 0; i < films.length; i++) {
    var film = films[i]
    if (!(film.title in titles)) {
      titles[film.title] = true
    }
  }
  var sorted_titles = Object.keys(titles).sort()
  $('#q').autocomplete({
    source: sorted_titles,
    minLength: 0,
    select: function (event, ui) {
      $('#q').val('"' + escape_reg_exp(ui.item.value) + '"')
      search()
      return false
    }
  })
}

function show_all_titles () {
  $('#q').autocomplete('search', '')
  $('#q').focus()
}

function show_all_markets () {
  $('#m').autocomplete('search', '')
  $('#m').focus()
}

var last_market = null
function build_market () {
  initialize_page()

  var current_market = selected_market()
  var new_market = !last_market || current_market !== last_market
  var did_initialize_storage = initialize_storage(new_market)
  last_market = current_market

  if (!did_initialize_storage) {
    status('Data fetched from session storage.')
    spinner.stop()
    show_titles()
    search()
    return
  }
  var status_message = 'Fetching Market Data...'
  var status_id = status(status_message)

  var url
  if (use_proxy) {
    url = `${api_url}?m=${current_market}`
  } else {
    url = `${api_url}/${current_market}`
  }

  $.when($.ajax({
    url: 'https://drafthouse.com/s/mother/v1/page/cclamp',
    type: 'GET',
    crossDomain: true,
    beforeSend: function (request) {
      request.setRequestHeader('Accept', 'application/json')
    },
    success: parse_markets
  }))

  $.when($.ajax({
    url: url,
    type: 'GET',
    crossDomain: true,
    beforeSend: function (request) {
      request.setRequestHeader('Accept', 'application/json')
    },
    success: parse_market
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
