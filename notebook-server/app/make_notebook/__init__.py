import docker
import psutil
from random import randint
import time

IMAGE = 'gsamharrison/plugin-test:1.0'
SLEEP_SECONDS = 3

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

def start_notebook():
    #start a docker on a random port from range container and detach from it 
    notebook_port = get_free_port()
    print(notebook_port)
    client = docker.from_env()
    container = client.containers.run(image=IMAGE,
      ports={8888:notebook_port},
      detach = True
    )
    # Wait for 5 seconds
    time.sleep(SLEEP_SECONDS)
    return notebook_port

if __name__ == '__main__':
    start_notebook()

#docker run -p 8888:8888 jupyter/scipy-notebook:2c80cf3537ca
