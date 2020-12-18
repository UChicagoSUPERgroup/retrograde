#stop stop and remove all docker containers
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
