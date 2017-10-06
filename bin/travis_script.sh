#!/usr/bin/env bash

export AUTODEPLOY_MESSAGE="deployment image update from travis_deploy_script"

if [ "${B64_ENV_FILE}" != "" ]; then
    echo "${B64_ENV_FILE}" | base64 -d > ".tmp-k8s-env"
    source ".tmp-k8s-env"
    mv .tmp-k8s-env "devops/k8s/.env.${K8S_ENVIRONMENT}"
fi

if [ "${TRAVIS_PULL_REQUEST}" != "false" ] || [ "${TRAVIS_BRANCH}" != "${CONTINUOUS_DEPLOYMENT_BRANCH}" ]; then
    echo " > running tests"
    if ! bin/test.sh; then
        echo " > Tests failed!"
        exit 1
    fi
    exit 0
fi

if echo "${TRAVIS_COMMIT_MESSAGE}" | grep "${AUTODEPLOY_MESSAGE}" > /dev/null; then
    echo " > skipping deployment - commit is autogenerated by this script - prevent infinite recursion"
    exit 0
fi

if [ "${DEPLOYMENT_BOT_GITHUB_TOKEN}" == "" ] || [ "${SERVICE_ACCOUNT_B64_JSON_SECRET_KEY}" == "" ]; then
    echo " > following environment variables are required for travis deploy: "
    echo " > (they should be created by provision script and set in travis env)"
    echo " > SERVICE_ACCOUNT_B64_JSON_SECRET_KEY"
    echo " > DEPLOYMENT_BOT_GITHUB_TOKEN"
    echo " > B64_ENV_FILE"
    exit 0
fi

export GIT_CONFIG_USER="${CONTINUOUS_DEPLOYMENT_GIT_USER}"
export GIT_CONFIG_EMAIL="${CONTINUOUS_DEPLOYMENT_GIT_EMAIL}"

echo " > install and authenticate with gcloud"  # based on http://thylong.com/ci/2016/deploying-from-travis-to-gce/

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

if [ ! -d "$HOME/google-cloud-sdk/bin" ]; then
    rm -rf $HOME/google-cloud-sdk
    curl https://sdk.cloud.google.com | bash
fi

source /home/travis/google-cloud-sdk/path.bash.inc
gcloud version
gcloud --quiet components update kubectl

export BUILD_LOCAL=1

IID_FILE="devops/k8s/iidfile-${K8S_ENVIRONMENT}-app"
OLD_APP_IID=`cat "${IID_FILE}"`

if ! bin/k8s_continuous_deployment.sh; then
    echo " > Failed continuous deployment"
    exit 1
else
    NEW_APP_IID=`cat "${IID_FILE}"`
    if [ "${OLD_APP_IID}" != "${NEW_APP_IID}" ]; then
        echo " > Committing app image change to GitHub"
        git config user.email "${GIT_CONFIG_EMAIL}"
        git config user.name "${GIT_CONFIG_USER}"
        git diff devops/k8s/values-${K8S_ENVIRONMENT}-image-app.yaml "${IID_FILE}"
        git add devops/k8s/values-${K8S_ENVIRONMENT}-image-app.yaml "${IID_FILE}"
        git commit -m "${AUTODEPLOY_MESSAGE}"
        git push "https://${DEPLOYMENT_BOT_GITHUB_TOKEN}@github.com/${TRAVIS_REPO_SLUG}.git" "HEAD:${TRAVIS_BRANCH}"
    fi
    echo " > done"
    exit 0
fi
