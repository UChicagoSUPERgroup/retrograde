"""
prompter: a tool for prompting documentation decisions
"""

import setuptools

setuptools.setup(
    name='prompter',
    version='0.1',
    description='Server-side extension ',
    author='Galen Harrison',
    author_email='harrisong@uchicago.edu',
#    url = 'https://github.com/mkery/Verdant',
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_data = {
        "" : ["*.sql"],
    },
)
