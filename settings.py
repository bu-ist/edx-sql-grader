import json
import logging
import os

from path import path

REPO_PATH = path(__file__).abspath().dirname()
ENV_ROOT = REPO_PATH.dirname()

CONFIG_PREFIX = "grader."

# Environment configuration file (i.e. /edx/app/grader.env.json)
with open(ENV_ROOT / CONFIG_PREFIX + "env.json") as env_file:
    ENV_TOKENS = json.load(env_file)

POLL_INTERVAL = ENV_TOKENS.get("POLL_INTERVAL", 5)

DAEMON_USER = ENV_TOKENS.get("DAEMON_USER", "edx")
DAEMON_GROUP = ENV_TOKENS.get("DAEMON_GROUP", "edx")

DAEMON_DEBUG = ENV_TOKENS.get("DEBUG", False)

# Logging
LOG_DIR = ENV_TOKENS.get("LOG_DIR", "/edx/app/logs/grader")
OUT_LOG = os.path.join(LOG_DIR, ENV_TOKENS.get("OUT_LOG", "daemon.out"))
DAEMON_LOG = os.path.join(LOG_DIR, ENV_TOKENS.get("DAEMON_LOG", "daemon.log"))

LOG_FORMAT = ENV_TOKENS.get("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
try:
    LOG_LEVEL = getattr(logging, ENV_TOKENS.get("LOG_LEVEL", ""))
except AttributeError:
    LOG_LEVEL = logging.ERROR


# Secrets configuration file (i.e. /edx/app/grader.auth.json)
with open(ENV_ROOT / CONFIG_PREFIX + "auth.json") as auth_file:
    AUTH_TOKENS = json.load(auth_file)

GRADER_CONFIG = AUTH_TOKENS['GRADER_CONFIG']
XQUEUE_INTERFACE = AUTH_TOKENS['XQUEUE_INTERFACE']
