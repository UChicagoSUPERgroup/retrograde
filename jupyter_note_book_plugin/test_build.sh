# script to build, install and test jupyter extension
pipenv run pip install jupyterlab
# pipenv run echo "import os; print(os.environ['JUPYTER_CONFIG_DIR'])" | python 
# it turns out that pipenv can't access to VIRTUAL_ENV env variable without 
# going into the shell. Therefore I did
# pipenv shell && echo 'JUPYTER_CONFIG_DIR='${VIRTUAL_ENV}'/etc/jupyter' > .env 
# note that you can't do this in the shell script I don't think b/c then VIRTUAL_ENV wouldn't be defined before entering the shell

rm ~/.promptml/cells.db
yes | pipenv run jupyter kernelspec uninstall -y prompt_kernel # want to overwrite in case already existing kernel
echo '{"argv" : ["python3", "'"$PWD"'/forking_kernel.py", "-f", "{connection_file}"], "display_name" : "prompter"}' > ./prompt_kernel/kernel.json
cd ./prompt-ml
pipenv run jlpm install
pipenv run jupyter labextension install

cd ..
cd ./serverextension


pipenv run python3 setup.py sdist bdist_wheel
pipenv run pip3 install -U -I dist/prompter-0.1-py3-none-any.whl
pipenv run jupyter serverextension enable --py prompter --debug
cd ..
pipenv run jupyter kernelspec install prompt_kernel
pipenv run jupyter lab ../evaluation_task --log-level=DEBUG --ip=127.0.0.1 --watch 
