import os


# Use directory in buildout/var/instance.
DIR = os.path.join(os.environ.get("CLIENT_HOME", ""), "exports")
# collective.jsonify puts 1000 files in a directory, so we don't reach some filesystem limit.
# That seems wise.
ITEMS_PER_DIR = 1000
