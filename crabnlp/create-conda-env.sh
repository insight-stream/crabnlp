#!/usr/bin/env sh

conda env create -f environment.yml
conda run -n crabnlp python -m pip install -e .
conda run -n crabnlp python -m ipykernel install --user
