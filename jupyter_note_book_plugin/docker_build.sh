# script to build, install and test jupyter extension
pipenv run pip install jupyterlab
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
pipenv run jupyter serverextension enable --py prompter --sys-prefix --debug
cd ..
export JUPYTER_CONFIG_DIR="./etc/jupyter"
pipenv run jupyter kernelspec install prompt_kernel
#pipenv run jupyter lab . --log-level=DEBUG --ip=127.0.0.1 --port=8888 #--watch 
