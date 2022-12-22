"""
Note: Requires fabric<2.0
"""

import logging
import os
import yaml

from fabric.api import lcd, task, local
from shutil import rmtree

USE_RSYNC_PROJECT = True

if USE_RSYNC_PROJECT:
    from fabric.api import env
    from fabric.contrib.project import rsync_project
    from functools import partial


logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger()
repo_root = local("git rev-parse --show-toplevel", capture=True)
workspace = local("mktemp -d", capture=True)
conf_file = "deploy.yaml"
ignore = [".git", "fabfile.py", "cache", "config", "*.log"]

try:
    conf = yaml.load(
        open(os.path.join(repo_root, conf_file), "rb").read(),
        Loader=yaml.Loader,
    )
except:
    log.exception("error: unable to read {} config file:".format(conf_file))
    raise

env.user = conf["user"]
env.hosts = ["{}@{}:22".format(env.user, host) for host in conf["hosts"]]


def export():
    """Exports repository's master branch to a temporary workspace."""
    with lcd(repo_root):
        local("git archive master | tar -x -C " + workspace)


def deploy_project(local_dir, remote_dir, exclude=[]):
    """Deploy the entire project at local_dir to remote_dir, excluding the given paths."""
    export()

    if USE_RSYNC_PROJECT:
        sync = partial(
            rsync_project,
            remote_dir=remote_dir,
            exclude=exclude,
            delete=True,
            extra_opts="-e 'ssh -l {}'".format(conf["user"]),
        )
    else:
        exclude = [".git", "fabfile.py", "cache", "config", "*.log", "js", "image"]
        cmd = "rsync -pthrvz --delete"
        cmd = (
            cmd
            + " {exclude} --rsh='ssh  -p 22 ' -e 'ssh -l {user}' {local_dir} {host}:{remote_dir}"
        )
        cmd_params = {
            "user": conf["user"],
            "host": conf["host"],
            "remote_dir": remote_dir,
            "exclude": " ".join("--exclude '{}'".format(x) for x in exclude),
        }

        def sync(local_dir):
            cmd_params["local_dir"] = local_dir
            local(cmd.format(**cmd_params))

    try:
        with lcd(workspace):
            with lcd(local_dir):
                sync(local_dir=".")
            sync(local_dir="resources")
    except:
        log.exception("deployment error:")
        raise
    finally:
        rmtree(workspace)


@task
def publish():
    """Publishes web implementation and resources to remote server."""
    deploy_project("web", conf["web_remote_dir"], exclude=ignore + ["template"])


@task
def deploy():
    """Deploys notification script to remote server."""
    deploy_project(
        "script", conf["script_remote_dir"], exclude=ignore + ["js", "image"]
    )
