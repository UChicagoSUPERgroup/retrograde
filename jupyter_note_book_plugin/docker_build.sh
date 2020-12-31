# script to build, install and test jupyter extension

rm ~/.promptml/cells.db
yes | jupyter kernelspec uninstall -y prompt_kernel # want to overwrite in case already existing kernel
echo '{"argv" : ["python3", "'"$PWD"'/forking_kernel.py", "-f", "{connection_file}"], "display_name" : "prompter"}' > ./prompt_kernel/kernel.json
#build datatask
cd ./evaluation_task
python3 build_task.py
cd ..
cd ./prompt-ml
jlpm install
jupyter labextension install

cd ..
cd ./serverextension
python3 setup.py sdist bdist_wheel
pip install -U -I dist/prompter-0.1-py3-none-any.whl
jupyter serverextension enable --py prompter --sys-prefix --debug
cd ..
export JUPYTER_CONFIG_DIR="./etc/jupyter"
jupyter kernelspec install prompt_kernel
yes | jupyter kernelspec uninstall -y python3
mv /usr/local/share/jupyter/kernels/prompt_kernel /usr/local/share/jupyter/kernels/python3 

# this disables pip, I think
rm /usr/local/bin/pip*
# apparently you just need to rename the kernel to disable python3 actually
#pipenv run jupyter lab . --log-level=DEBUG --ip=127.0.0.1 --port=8888 #--watch 
