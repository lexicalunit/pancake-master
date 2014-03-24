import logging
import os
import yaml

from fabric.api import lcd, env, task, local
from fabric.contrib.project import rsync_project


logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger()
repo_root = local('git rev-parse --show-toplevel', capture=True)
conf_file = 'deploy.yaml'

try:
    conf = yaml.load(open(os.path.join(repo_root, conf_file), 'rb').read())
except:
    log.exception('error: unable to read {} config file:'.format(conf_file))

env.user = conf['user']
env.hosts = ['{}@{}:22'.format(env.user, host) for host in conf['hosts']]


def deploy_project(local_dir, remote_dir, exclusions=[]):
    """Deploy the entire project at local_dir to remote_dir, excluding the given paths."""
    with lcd(repo_root):
        with lcd(local_dir):
            rsync_project(remote_dir=remote_dir, local_dir='.', exclude=exclusions)
        rsync_project(remote_dir=remote_dir, local_dir='resources', exclude=exclusions, delete=True)


@task
def deploy():
    """Deploys web and script to remote server."""
    deploy_project('web', conf['web_remote_dir'],
                   ['.git', 'fabfile.py', 'cache', 'config', 'template'])
    deploy_project('script', conf['script_remote_dir'],
                   ['.git', 'fabfile.py', 'cache', 'js', 'image'])
