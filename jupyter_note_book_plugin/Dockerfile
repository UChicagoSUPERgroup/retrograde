FROM python:3.7-slim
#Download Node into Container
RUN apt-get update
RUN apt-get -y install curl gnupg
RUN curl -sL https://deb.nodesource.com/setup_14.x  | bash -
RUN apt-get -y install nodejs
#Install pipenv and run the build script
ADD . /
RUN chmod +x docker_build.sh
#Run the installation script
RUN pip install -r /requirements.txt
RUN  /docker_build.sh
CMD jupyter lab ./evaluation_task --log-level=DEBUG --port=8888 --no-browser --allow-root --ip=0.0.0.0 --NotebookApp.token='' --NotebookApp.password=''
