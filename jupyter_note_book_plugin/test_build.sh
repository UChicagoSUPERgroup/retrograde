BUILD_FRONTEND=${BUILD_FRONTEND:-0}

while [ $# -gt 0 ]; do

    if [[ $1 == *"--"* ]]; then
        param="${1/--/}"
        declare $param="$2"
    fi

    shift
done

source ~/miniconda3/etc/profile.d/conda.sh
conda activate plugin_conda
pip install -r requirements.txt
rm ~/.promptml/cells.db
yes | jupyter kernelspec uninstall -y prompt_kernel # want to overwrite in case already existing kernel
echo '{"argv" : ["python3", "'"$PWD"'/forking_kernel.py", "-f", "{connection_file}"], "display_name" : "prompter"}' > ./prompt_kernel/kernel.json

if [[ $INSTALL_FRONTEND -eq 1 ]]; then
    cd ./prompt-ml
    jlpm install
    jupyter labextension install
    cd ..
fi

if [[ $BUILD_FRONTEND -eq 1 ]]; then
    cd ./prompt-ml && jupyter lab build && cd ..
fi

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

