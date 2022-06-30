from flask import Flask, Response
import shutil
import os
import git
from git import Git, Repo
import base64
import mimetypes
import json
from sesamutils.flask import serve
from sesamutils import sesam_logger

envs = os.environ

git_repo = envs['GIT_REPO']  # must be on the form git@(...).git
deploy_token = envs['DEPLOY_TOKEN']
refresh = os.environ.get('REFRESH', 'true') == 'true'  # if true, pulls latest version of repo if it already exists
branch = os.environ.get('BRANCH', 'master')
sparse = os.environ.get('SPARSE', 'false') == 'true'

dataset = {}
base = "/filelisting"

if os.environ.get('RUNNING_LOCALLY', 'false') == 'true':
    git_cloned_dir = "/tmp/git_clone/%s" % branch
else:
    git_cloned_dir = "/data/git_clone/%s" % branch

app = Flask(__name__)
logger = sesam_logger('github-service', app=app)


@app.route('/', methods=['GET'])
def root():
    return Response(status=200, response="I am Groot!")


@app.route('/filelisting', methods=['GET'])
def get_entities():
    """
    Returns a JSON array containing all entities in the git repository (except files in .git).
    """

    logger.info("Got request to retrieve all files in repo")
    try:
        if not os.path.exists(git_cloned_dir):
            clone_repo()
        elif refresh:
            pull_repo()

        # Build dataset if it is empty, ignoring .git folder
        if not dataset or refresh:
            build_dataset()

        return Response(json.dumps(dataset))

    except BaseException as e:
        logger.warning(f"Unable to retrieve files due to an exception:\n%s" % e)
        raise e


@app.route('/filelisting/<path:path>', methods=['GET'])
def get_file_or_folder(path):
    """
    Fetch a specific file/folder and serve it as a JSON. If a folder is requested, a JSON array containing all
    entities in that folder is returned.
    """

    logger.info("Got request to retrieve file '%s'" % path)
    try:
        if not os.path.exists(git_cloned_dir):
            clone_repo()
        elif refresh:
            pull_repo()

        paths = path.split("/")

        # Checkout appropriate path if file/folder does not exist
        if sparse:
            filesystem_path = os.path.join(git_cloned_dir, path)
            if not os.path.isfile(filesystem_path):
                repo = git.Repo(git_cloned_dir)
                os.chdir(git_cloned_dir)
                repo.git.sparse_checkout("set", path)
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
                logger.info("Retrieved file '%s' with content type %s" % (path, entity["content-type"]))
            except StopIteration:
                return Response(status=404, response="Unable to retrieve entity with _id '%s'" % ('/' + path))

        if not isinstance(entity, list):
            entity = [entity]

        return Response(json.dumps(entity), mimetype='application/json')

    except BaseException as e:
        logger.warning(f"Unable to retrieve file or file contents due to an exception:\n%s" % e)
        raise e


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
    if not os.path.exists('id_deployment_key'):
        with open("id_deployment_key", "w") as key_file:
            key_file.write(deploy_token)
            os.chmod("id_deployment_key", 0o600)

    ssh_cmd = 'ssh -o "StrictHostKeyChecking=no" -i id_deployment_key'
    logger.info(f"Cloning branch '{branch}' of Git repo '{git_repo}'")

    remove_if_exists(git_cloned_dir)

    repo = git.Repo.clone_from(
        git_repo,
        git_cloned_dir,
        sparse=sparse,
        env=dict(GIT_SSH_COMMAND=ssh_cmd),
        branch=branch
    )


def pull_repo():
    if not os.path.exists('id_deployment_key'):
        with open("id_deployment_key", "w") as key_file:
            key_file.write(deploy_token)
            os.chmod("id_deployment_key", 0o600)

    ssh_cmd = 'ssh -o "StrictHostKeyChecking=no" -i id_deployment_key'
    logger.info(f"Pulling newest version of branch '{branch}' of Git repo '{git_repo}'")

    repo = git.Repo(git_cloned_dir)

    with repo.git.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
        repo.git.checkout(branch)
        repo.git.pull()


def remove_if_exists(path):
    if os.path.exists(path):
        for root, dirs, files in os.walk(path):
            shutil.rmtree(path)


if __name__ == '__main__':
    serve(app)
