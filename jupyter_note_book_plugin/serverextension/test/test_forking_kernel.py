"""
tests for forking kernel
"""
from context import prompter


if __name__ == "__main__":
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=prompter.RemoteForkingKernel)

