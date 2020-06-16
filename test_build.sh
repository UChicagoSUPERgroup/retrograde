# script to build, install and test jupyter extension

cd ./serverextension
python3 setup.py sdist bdist_wheel
pip3 install -U -I dist/prompter-0.1-py3-none-any.whl
jupyter serverextension enable --py prompter --sys-prefix --debug
cd ..
export JUPYTER_CONFIG_DIR="./etc/jupyter"

rm ~/.promptml/cells.db

jupyter lab . --log-level=DEBUG --watch 
