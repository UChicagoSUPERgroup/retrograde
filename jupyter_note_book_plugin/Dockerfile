FROM python:3.7-slim
#Download Node into Container
RUN apt-get update
RUN apt-get -y install curl gnupg
RUN curl -sL https://deb.nodesource.com/setup_14.x  | bash -
RUN apt-get -y install nodejs
RUN apt-get update && apt-get install gcc -y
#Install pipenv and run the build script
ADD . /
RUN chmod +x docker_build.sh
#run the docker image in jupyter_note_book_plugin/evaluation_task/
RUN chmod +x run_image.sh
#Run the installation script
RUN pip install -r /requirements.txt
RUN  /docker_build.sh

# call run_image on container start -> access env variables
