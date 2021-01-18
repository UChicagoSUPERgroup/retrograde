source ~/miniconda3/etc/profile.d/conda.sh
conda activate plugin_conda
pip install -r requirements.txt
rm ~/.promptml/cells.db
yes | jupyter kernelspec uninstall -y prompt_kernel # want to overwrite in case already existing kernel
echo '{"argv" : ["python3", "'"$PWD"'/forking_kernel.py", "-f", "{connection_file}"], "display_name" : "prompter"}' > ./prompt_kernel/kernel.json
cd ./prompt-ml
jlpm install
jupyter labextension install
cd ..
cd ./serverextension
python3 setup.py sdist bdist_wheel
pip3 install -U -I dist/prompter-0.1-py3-none-any.whl
jupyter serverextension enable --py prompter --debug
mysql -u root -p < prompter/make_db.sql
mysql -u root -p notebooks < prompter/make_tables.sql
cd ..
jupyter kernelspec install prompt_kernel
cd ./evaluation_task
python build_task.py
cd ../
jupyter lab ./evaluation_task --log-level=DEBUG --ip=127.0.0.1 #--watch 

