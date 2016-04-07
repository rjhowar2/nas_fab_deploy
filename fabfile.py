from __future__ import with_statement
from git import Repo
from fabric.api import  env, run, sudo, task, cd, prefix
from fabric.operations import prompt
from fabric.contrib.console import confirm
from fabric.context_managers import shell_env
from contextlib import contextmanager

import os
import uuid
import string
import random
import socket

env.hosts=["localhost"]
env.file_server_directory = os.path.join(os.path.abspath(os.pardir), "file_server")
env.web_app_directory = os.path.join(os.path.abspath(os.pardir), "web_app")
env.file_server_activate = "source %s" % (os.path.join(env.file_server_directory, "activate"))
env.web_app_activate = "source %s" % (os.path.join(env.web_app_directory, "activate"))
env.file_server_pid = os.path.join(env.file_server_directory, "pid")
env.web_app_pid = os.path.join(env.web_app_directory, "pid")

WEB_APP_GIT_URL = "https://github.com/rjhowar2/easyNAS"
FILE_SERVER_GIT_URL = "https://github.com/rjhowar2/nas-file-server"

@contextmanager
def _file_server_venv():
    with cd(env.file_server_directory):
        with prefix(env.file_server_activate):
            yield

@contextmanager
def _web_app_venv():
    with cd(env.web_app_directory):
        with prefix(env.web_app_activate):
            yield
def _valid_app(name):
    return name in ["all", "web_app", "file_server"]

def _deploy_web_app(init_db=True):
    print ("Deploying Web App")
    with _web_app_venv():
        run("pip install -r requirements.txt")
        with shell_env(DJANGO_SETTINGS_MODULE="easyNAS.settings.dev"):
            if(init_db):
                run("python manage.py migrate")
                run("python manage.py createsuperuser")
            
            run("gunicorn -b 0.0.0.0:8000 -p %s -D easyNAS.wsgi" % env.web_app_pid)

def _deploy_file_server():
    print ("Deploying Web App")
    with _file_server_venv():
        run("pip install -r requirements.txt")
        run('python -c "from nas_server.tests.test_utils import *; rebuild_test_tree()"')
        run("gunicorn -b 0.0.0.0:5000 -p %s -D runserver:app" % env.file_server_pid)

@task
def build_app():
    #builds full app, runs all steps

    #Clone all required repos from GIT
    clone()
    build_configs()
    _deploy_file_server()

    if confirm("Deploy web app locally?"):
        _deploy_web_app(init_db=True)

@task
def clone(app_name="all"):
    if not _valid_app(app_name):
        print "%s is not a valid app name" % app_name
        return

    if app_name in ["all", "web_app"]:
        run("rm -rf %s" % env.web_app_directory)
        run("mkdir %s" % env.web_app_directory)
        Repo.clone_from(WEB_APP_GIT_URL, env.web_app_directory)

        # Create virtual environment
        with cd(env.web_app_directory):
            run("virtualenv venv")
            run("ln -s venv/bin/activate activate")
    if app_name in ["all", "file_server"]:
        run("rm -rf %s" % env.file_server_directory)
        run("mkdir %s" % env.file_server_directory)
        Repo.clone_from(FILE_SERVER_GIT_URL, env.file_server_directory)

        # Create virtual environment
        with cd(env.file_server_directory):
            run("virtualenv venv")
            run("ln -s venv/bin/activate activate")

@task
def build_configs():
    #generate a unique client id and secret to be shared across the apps
    client_id = 'CLIENT_ID="%s"' % (str(uuid.uuid4()))
    client_secret = 'CLIENT_SECRET="%s"' % (''.join((random.choice(string.letters + string.digits)) for x in range(16)))

    #create config files and store in both locations
    run("echo '%s' >> %s" % (client_id, os.path.join(env.web_app_directory, "easyNAS/settings/common.py")))
    run("echo '%s' >> %s" % (client_secret, os.path.join(env.web_app_directory, "easyNAS/settings/common.py")))

    run("echo '%s' >> %s" % (client_id, os.path.join(env.file_server_directory, "nas_server/config.py")))
    run("echo '%s' >> %s" % (client_secret, os.path.join(env.file_server_directory, "nas_server/config.py")))
    
    #prompt for any additional config file info and store it
    host_ip = socket.gethostbyname(socket.gethostname())
    api_url = 'FILE_SERVER_BASE_URL="http://%s:5000/nas_server/api/v1.0"' % host_ip

    files_dir = prompt("Please enter the location of the shared folder")
    if files_dir:
        files_dir = 'FILES_DIRECTORY="%s"' % files_dir
        run("echo '%s' >> %s" % (files_dir, os.path.join(env.file_server_directory, "nas_server/config.py")))

    run("echo '%s' >> %s" % (api_url, os.path.join(env.web_app_directory, "easyNAS/settings/common.py")))

@task
def deploy(app_name):
    if app_name == "web_app":
        _deploy_web_app()
    elif app_name == "file_server":
        _deploy_file_server()

@task
def kill(app_name="all"):
    if not _valid_app(app_name):
        print "%s is not a valid app name" % app_name
        return
    if app_name in ["web_app", "all"]:
        run("kill -9 `cat %s`" % env.web_app_pid)
    if app_name in ["file_server", "all"]:
        run("kill -9 `cat %s`" % env.file_server_pid)
        