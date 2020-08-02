# prompt-ml

Prompt data scientists to identify and consider decisions they have made during the analysis of data or building of an ml model


## Prerequisites

* JupyterLab

## Installation

```bash
jupyter labextension install prompt-ml
```

## Development

For a development install (requires npm version 4 or later), do the following in the repository directory:

```bash
npm install
npm run build
jupyter labextension link .
```

To rebuild the package and the JupyterLab app:

```bash
npm run build
jupyter lab build
```

