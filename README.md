# ctxssg

[![PyPI](https://img.shields.io/pypi/v/ctxssg.svg)](https://pypi.org/project/ctxssg/)
[![Changelog](https://img.shields.io/github/v/release/kgruel/ctxssg?include_prereleases&label=changelog)](https://github.com/kgruel/ctxssg/releases)
[![Tests](https://github.com/kgruel/ctxssg/actions/workflows/test.yml/badge.svg)](https://github.com/kgruel/ctxssg/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/kgruel/ctxssg/blob/master/LICENSE)

contextual docs

## Installation

Install this tool using `pip`:
```bash
pip install ctxssg
```
## Usage

For help, run:
```bash
ctxssg --help
```
You can also use:
```bash
python -m ctxssg --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd ctxssg
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```
