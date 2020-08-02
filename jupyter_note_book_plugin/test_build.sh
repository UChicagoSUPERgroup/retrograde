# script to build, install and test jupyter extension
pipenv run pip install -r requirements.txt
cd ./prompt-ml
pipenv run jlpm install
pipenv run jupyter labextension install --no-build
cd ..
cd ./serverextension
pipenv run python3 setup.py sdist bdist_wheel
pipenv run pip3 install -U -I dist/prompter-0.1-py3-none-any.whl
pipenv run jupyter serverextension enable --py prompter --sys-prefix --debug
cd ..
export JUPYTER_CONFIG_DIR="./etc/jupyter"

rm ~/.promptml/cells.db

pipenv run jupyter lab . --log-level=DEBUG #--watch 
