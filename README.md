# Github service
A microservice that provides the contents of a file in a given Github repository. The 
contents are base64 encoded and served over HTTP. For private repositories, a deploy token 
with sufficient access rights must be provided.

## Environment variables
``GIT_REPO`` - The SSH URL to the repository containing the target file.
Example: git@github.com:some-community/your-repo.git

``FILE_PATH`` - The path to the file. The branch of the repository must be included in the path, for
example /master/directory/your-file.extension

``DEPLOY_TOKEN`` - The private deploy key with clone repo rights. The same key should be added to 
your Sesam node so that it can be specified as a secret. Example: $SECRET(your-deploy-token)

``REFRESH`` - If true, the repository will be cloned after each request, even if the repository
already exists. Default: true

``SPARSE`` - If true, only the files specified with FILE_PATH are cloned, rather than cloning the
entire repository. Default: false