FROM python:3.7-slim
#Download Node into Container
RUN apt-get update
RUN apt-get update && apt-get install gcc -y
RUN apt-get -y install gnupg curl
RUN curl -sL https://deb.nodesource.com/setup_14.x  | bash -
RUN apt-get -y install nodejs
RUN rm -rf /usr/bin/apt-get
RUN rm -rf /usr/bin/apt
#Install pipenv and run the build script
ADD . /
RUN mkdir -p /etc/jupyter/lab/workspaces 
RUN touch /Pipfile
RUN useradd -m -r -g users A && \
chown -R A:users /evaluation_task && \
chown -R A:users /etc/jupyter/lab/workspaces
# RUN chmod +x docker_build.sh
#run the docker image in jupyter_note_book_plugin/evaluation_task/
RUN chmod o-r /Dockerfile
RUN chmod o-r /Pipfile
RUN chmod o-r /root /bin /dev /home /lib /lib64 /opt /prompt-ml /prompt_kernel /serverextension
RUN chmod +x run_image.sh
#Run the installation script
RUN pip install -r /requirements.txt
RUN echo '{"argv" : ["python3", "'"$PWD"'/forking_kernel.py", "-f", "{connection_file}"], "display_name" : "retrograde"}' > ./prompt_kernel/kernel.json
RUN cd ./evaluation_task && python3 build_task.py
RUN cd ./prompt-ml && jlpm install && jupyter labextension install
WORKDIR "./serverextension"
RUN python3 setup.py sdist bdist_wheel
RUN pip install -U -I dist/prompter-0.1-py3-none-any.whl
RUN jupyter serverextension enable --py prompter --sys-prefix --debug
WORKDIR "/"
ENV JUPYTER_CONFIG_DIR="./etc/jupyter"
RUN jupyter kernelspec install prompt_kernel
RUN yes | jupyter kernelspec uninstall -y python3
RUN mv /usr/local/share/jupyter/kernels/prompt_kernel /usr/local/share/jupyter/kernels/python3
RUN rm /usr/local/bin/pip*
RUN rm -r /usr/local/lib/python3.7/site-packages/pip*
# call run_image on container start -> access env variables
