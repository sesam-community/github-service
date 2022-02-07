# Github service
A microservice that provides the contents of a file in a given Github repository. The 
contents are base64 encoded and served over HTTP. For private repositories, a deploy token 
with sufficient access rights must be provided.

## Environment variables
``GIT_REPO`` - The SSH URL to the repository containing the target file.
Example: git@github.com:some-community/your-repo.git

``DEPLOY_TOKEN`` - The private deploy key with clone repo rights. The same key should be added to 
your Sesam node so that it can be specified as a secret. Example: $SECRET(your-deploy-token)

``REFRESH`` - If true, the repository will be cloned after each request, even if the repository
already exists. Default: true

``BRANCH`` - Which branch of the repository to retrieve files from. Default: master

``SPARSE`` - If true, only the files specified with FILE_PATH are cloned, rather than cloning the
entire repository. Default: false

## Example setup

System:
````
{
  "_id": "my-github-service",
  "type": "system:microservice",
  "docker": {
    "environment": {
      "DEPLOY_TOKEN": "$SECRET(deploy-token)",
      "GIT_REPO": "git@github.com:my_community/my_repo.git",
    },
    "image": "sesamcommunity/github-service:<version>",
    "port": 5000
  }
}
````

Pipe:

When specifying the path to the file or folder in the Github repository, the path must be
prefixed with ``/filelisting/entities``:
````
...
  {
  "source": {
    "type": "json",
    "system": "my-github-service",
    "url": "/filelisting/entities/path/to/file"
  },
...
````