# this is to access env variables passed in at runtime
echo $JP_PLUGIN_USER
echo $MODE
jupyter lab ./evaluation_task --log-level=DEBUG --no-browser --allow-root --port=$PLUGIN_PORT --ip=0.0.0.0 --NotebookApp.token='' --NotebookApp.password=''
