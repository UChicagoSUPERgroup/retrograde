FROM python:3.7-slim
#Download Node into Container
RUN apt-get update
RUN apt-get -y install curl gnupg
RUN curl -sL https://deb.nodesource.com/setup_14.x  | bash -
RUN apt-get -y install nodejs
#Install pipenv and run the build script
RUN pip install pipenv
RUN pipenv --python 3.7
ADD . /
RUN chmod +x test_build.sh
#Run the installation script
RUN  /test_build.sh
CMD pipenv run jupyter lab . --log-level=DEBUG --port=8888 --no-browser --allow-root --ip=0.0.0.0