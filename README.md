# Pancake Master

![preview](https://cloud.githubusercontent.com/assets/1903876/16548471/128994b0-4155-11e6-8c05-0db6efa91c01.png)

Pancake Master is two separate components: A python notification script which hits the Drafthouse API and looks for any relevant updates, and a dynamic webpage component that hits the same API and uses AJAX to render the information in a web browser.

## Notification Script

Python script that searches for Master Pancake showtimes in Austin. Run it periodically to send out email notifications for newly detected or newly on-sale pancakes. Never miss out on getting tickets again! See requirements.txt for dependencies. For help pass `-h` or `--help` as a command line argument to the script.

## Dynamic Webpage

Static HTML+AJAX solution which fetches and displays the most up-to-date Master Pancake information. Publish to a webserver with dependencies pancake.css, jquery, and underscore. [See it live](http://lexicalunit.github.io/pancake-master) on GitHub pages!

## Deploying and Publishing

[Fabric](http://www.fabfile.org/) handles deploying and publishing. [YAML](http://pyyaml.org/) handles configuration of your deployments and publishing information. Install both first before proceeding. You must also create a `deploy.yaml` configuration file within the root of your clone of this repository. It must follow this format:

```yaml
user: 'you@domain.com'
hosts: ['domain.com']
web_remote_dir: '/path/to/publish/your/www/html'
script_remote_dir: '/path/to/deploy/your/script'
```

> **NOTE:** Publishing and deploying require SSH access to your webspace.

### Deploying the Notification Script

```shell
cd /path/to/pancake-master
fab deploy
```

### Publishing the Dynamic Webpage

```shell
cd /path/to/pancake-master
fab publish
```

---

[MIT][mit] © [lexicalunit][author] et [al][contributors]

[mit]:              http://opensource.org/licenses/MIT
[author]:           http://github.com/lexicalunit
[contributors]:     https://github.com/lexicalunit/pancake-master/graphs/contributors
