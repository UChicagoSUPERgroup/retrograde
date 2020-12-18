"""
this runs the kernel that logs namespaces
"""

from prompter import ForkingKernel

if __name__ == "__main__":
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=ForkingKernel)
