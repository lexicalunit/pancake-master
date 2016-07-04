# Pancake Master

![preview](https://cloud.githubusercontent.com/assets/1903876/16548471/128994b0-4155-11e6-8c05-0db6efa91c01.png)

Pancake Master is two separate components: A python notification script which hits the Drafthouse API and looks for any relevant updates, and a dynamic webpage component that hits the same API and uses AJAX to render the information in a web browser.

## Notification Script

Python script that searches for Master Pancake showtimes in Austin. Run it periodically to send out email notifications for newly detected or newly on-sale pancakes. Never miss out on getting tickets again! See requirements.txt for dependencies.

## Dynamic Webpage

Static HTML+AJAX solution which fetches and displays the most up-to-date Master Pancake information. Deploy to a webserver with dependencies pancake.css, jquery, and underscore. [See it live](http://lexicalunit.github.io/pancake-master) on GitHub pages!

---

[MIT][mit] © [lexicalunit][author] et [al][contributors]

[mit]:              http://opensource.org/licenses/MIT
[author]:           http://github.com/lexicalunit
[contributors]:     https://github.com/lexicalunit/pancake-master/graphs/contributors
