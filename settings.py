import json
from path import path

REPO_PATH = path(__file__).dirname()
ENV_ROOT = REPO_PATH.dirname()

CONFIG_PREFIX = "grader."

# Environment configuration file (i.e. /edx/app/grader.env.json)
with open(ENV_ROOT / CONFIG_PREFIX + "env.json") as env_file:
    ENV_TOKENS = json.load(env_file)

POLL_INTERVAL = ENV_TOKENS.get("POLL_INTERVAL", 5)
LOG_LEVEL = ENV_TOKENS.get("LOG_LEVEL", "WARNING")

# Secrets configuration file (i.e. /edx/app/grader.auth.json)
with open(ENV_ROOT / CONFIG_PREFIX + "auth.json") as auth_file:
    AUTH_TOKENS = json.load(auth_file)

DATABASE = AUTH_TOKENS['DATABASE']
XQUEUE_INTERFACE = AUTH_TOKENS['XQUEUE_INTERFACE']
