from __future__ import with_statement
from git import Repo
from fabric.api import  env, run, sudo, task, cd, prefix
from fabric.operations import prompt
from fabric.contrib.console import confirm
from contextlib import contextmanager

import os
import uuid
import string
import random
import socket

env.hosts=["localhost"]
env.file_server_directory = os.path.join(os.path.abspath(os.pardir), "file_server")
env.web_app_directory = os.path.join(os.path.abspath(os.pardir), "web_app")
env.file_server_activate = "source %s" % (os.path.join(env.file_server_directory, "venv/bin/activate"))
env.web_app_activate = "source %s" % (os.path.join(env.web_app_directory, "venv/bin/activate"))

WEB_APP_GIT_URL = "https://github.com/rjhowar2/easyNAS"
FILE_SERVER_GIT_URL = "https://github.com/rjhowar2/nas-file-server"

@task
def build_app():
    #builds full app, runs all steps

    #Clone all required repos from GIT
    clone_repos()
    generate_configs()
    _deploy_file_server()

    if confirm("Deploy web app locally?"):
        _deploy_web_app()

@task
def clone_repos():
    run("mkdir %s" % env.web_app_directory)
    Repo.clone_from(WEB_APP_GIT_URL, env.web_app_directory)

    run("mkdir %s" % env.file_server_directory)
    Repo.clone_from(FILE_SERVER_GIT_URL, env.file_server_directory)

@task
def generate_configs():
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
    api_url = 'FILE_SERVER_URL="http://%s:5000/nas_server/api/v1.0"' % host_ip

    run("echo '%s' >> %s" % (api_url, os.path.join(env.web_app_directory, "easyNAS/settings/common.py")))

@task
def deploy(app_name):
    if app_name == "web_app":
        _deploy_web_app()
    elif app_name == "file_server":
        _deploy_file_server()

@contextmanager
def _file_server_venv():
    with cd(env.file_server_directory):
        run("virtualenv venv")
        with prefix(env.file_server_activate):
            yield

@contextmanager
def _web_app_venv():
    with cd(env.web_app_directory):
        run("virtualenv venv")
        with prefix(env.web_app_activate):
            yield

def _deploy_web_app():
    print ("Deploying Web App")
    with _web_app_venv():
        run("pip install -r requirements.txt")
        run("export DJANGO_SETTINGS_MODULE=easyNAS.settings.dev")
        run("python manage.py runserver 0.0.0.0:8000")

def _deploy_file_server():
    print ("Deploying Web App")
    with _file_server_venv():
        run("pip install -r requirements.txt")
        run("python runserver.py")
        # Still needs to run in the background :(
