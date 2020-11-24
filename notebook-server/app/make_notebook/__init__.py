import docker
import psutil
from random import randint
import time
import secrets

IMAGE = 'gsamharrison/plugin-test:1.9.2'

def get_free_port():
    lower_port = 8000
    upper_port = 9000
    port = randint(lower_port,upper_port)
    portsinuse=[]
    conns = psutil.net_connections()
    port = None
    for conn in conns:
        portsinuse.append(conn.laddr[1])
    for i in range(lower_port, upper_port):
        if i in portsinuse:
            continue
        else:
         port = i
         break
    if not port:
        raise ValueError('All ports in use...')
    return port

def start_notebook(prolific_id=None, mode=None):
    #start a docker on a random port from range container and detach from it 
    notebook_port = get_free_port()
    client = docker.from_env()

    env = {"DOCKER_HOST_IP" : "127.0.0.1", "PLUGIN_PORT" : notebook_port}
     
    if not prolific_id:
        env["JP_PLUGIN_USER"] = "UNTRACKED_USER-"+str(notebook_port)+str(randint(0,50))
    else:
        env["JP_PLUGIN_USER"] = prolific_id
    
    if not mode:
        env["MODE"] = "EXP_END"
    else:
        env["MODE"] = mode

    env["TOKEN"] = prolific_id

    container = client.containers.run(image=IMAGE,
     # ports={8888:notebook_port},
      command="bash ./run_image.sh",
      detach = True,
      network_mode = "host",
      environment = env, 
    )
    while (container.status == 'restarting' or container.status == 'created'):
        container.reload()
    return notebook_port, container.id

def stop_notebook(container_id):
    client = docker.from_env()
    container = client.containers.get(container_id)
    #wait 1 second to stop container, default is 10
    container.stop(timeout = 1)

if __name__ == '__main__':
    start_notebook()

#docker run -p 8888:8888 jupyter/scipy-notebook:2c80cf3537ca
