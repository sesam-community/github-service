from flask import Flask, Response
import cherrypy
import logging
import paste.translogger
import shutil
import os
import git
import base64
import mimetypes
import json

envs = os.environ

git_repo = envs['GIT_REPO']  # must be on the form git@(...).git
deploy_token = envs['DEPLOY_TOKEN']
refresh = os.environ.get('REFRESH', 'true') == 'true'  # if true, pulls latest version of repo if it already exists
branch = os.environ.get('BRANCH', 'master')
sparse = os.environ.get('SPARSE', 'false') == 'true'

dataset = {}
base = "/entities"
git_cloned_dir = "/data/git_clone/%s" % branch

app = Flask(__name__)
logger = logging.getLogger("datasource-service")


@app.route('/', methods=['GET'])
def root():
    return Response(status=200, response="I am Groot!")


@app.route('/entities', methods=['GET'])
def get_entities():
    """
    Returns a JSON array containing all entities in the git repository (except files in .git).
    """

    if not os.path.exists(git_cloned_dir):
        clone_repo()
    elif refresh:
        pull_repo()

    # Build dataset if it is empty, ignoring .git folder
    if not dataset or refresh:
        build_dataset()

    return Response(json.dumps(dataset))


@app.route('/entities/<path:path>', methods=['GET'])
def get_file_or_folder(path):
    """
    Fetch a specific file/folder and serve it as a JSON. If a folder is requested, a JSON array containing all
    entities in that folder is returned.
    """

    if not os.path.exists(git_cloned_dir):
        clone_repo()

    paths = path.split("/")

    # Checkout containing folder if input path is deeper than the root of the repo, or if file/folder does not exist
    if sparse:
        filesystem_path = os.path.join(git_cloned_dir, path)
        if len(paths) > 1 or not os.path.isfile(filesystem_path):
            repo = git.Repo(git_cloned_dir)
            os.chdir(git_cloned_dir)
            repo.git.sparse_checkout("set", paths[0])
            os.chdir(os.path.abspath(os.path.dirname(__file__)))   # return to service path

    build_dataset()   # update entities

    # Determine parent folder containing the requested file
    if len(paths) > 1:
        parent_folder = os.path.join(base, '/'.join(paths[:-1]))
    else:  # file is in the repository root
        parent_folder = base

    # Check first if the requested file is a folder. The keys in 'dataset' all represent folders in the repository.
    if os.path.join(base, path) in list(dataset.keys()):
        entity = dataset[os.path.join(base, path)]
    else:
        # If it is not a folder, find the containing folder 'subdict' and then look for the entity there
        subdict = dataset[os.path.join(base, parent_folder)]
        try:
            entity = next(item for item in subdict if item["_id"] == '/' + path)
        except StopIteration:
            return Response(status=404, response="Unable to retrieve entity with _id '%s'" % ('/' + path))

    return Response(json.dumps(entity))


def build_dataset():
    """
    Populate the dataset with files currently inside the git repository. The files in the .git folder are ignored.
    Each file is served as a Base64 encoded string.
    """

    for root, dirs, files in os.walk(git_cloned_dir):
        if '.git' not in root:
            key = base + str(root.split(git_cloned_dir)[1])
            dataset[key] = []  # each entry in 'dataset' is a list containing dicts
            for file in files:
                full_path = os.path.join(root, file)

                # Create entity with encoded file contents, identifier and content type
                with open(full_path, "rb") as open_file:
                    data = open_file.read()

                base64_bytes = base64.b64encode(data)
                content = str(base64_bytes, encoding="utf-8")
                _id = full_path.split(git_cloned_dir)[1]

                entity = {"_id": _id,
                          "content-type": mimetypes.guess_type(full_path)[0],
                          "content": content}

                dataset[key].append(entity)


def clone_repo():
    with open("id_deployment_key", "w") as key_file:
        key_file.write(deploy_token)

    os.chmod("id_deployment_key", 0o600)

    ssh_cmd = 'ssh -o "StrictHostKeyChecking=no" -i id_deployment_key'
    logging.info('cloning %s', git_repo)

    remove_if_exists(git_cloned_dir)

    repo = git.Repo.clone_from(
        git_repo,
        git_cloned_dir,
        sparse=sparse,
        env=dict(GIT_SSH_COMMAND=ssh_cmd),
        branch=branch
    )


def pull_repo():
    logging.info('pulling %s', git_repo)
    repo = git.Repo(git_cloned_dir)
    o = repo.remotes.origin
    o.pull()


def remove_if_exists(path):
    if os.path.exists(path):
        for root, dirs, files in os.walk(path):
            shutil.rmtree(path)


if __name__ == '__main__':
    format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Log to stdout, change to or add a (Rotating)FileHandler to log to a file
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(stdout_handler)

    # Comment these two lines if you don't want access request logging
    app.wsgi_app = paste.translogger.TransLogger(app.wsgi_app, logger_name=logger.name,
                                                 setup_console_handler=False)
    app.logger.addHandler(stdout_handler)

    logger.propagate = False
    logger.setLevel(logging.INFO)

    cherrypy.tree.graft(app, '/')

    # Set the configuration of the web server to production mode
    cherrypy.config.update({
        'environment': 'production',
        'engine.autoreload_on': False,
        'log.screen': True,
        'server.socket_port': 5000,
        'server.socket_host': '0.0.0.0'
    })

    # Start the CherryPy WSGI web server
    cherrypy.engine.start()
    cherrypy.engine.block()
