#!/usr/bin/env bash

for p in notebooks/*.ipynb; do
    f=`basename $p`
    [[ "$f" =~ ^[0-9].*$ ]] && continue


    conda run -n jupyter jupyter nbconvert --to python "$p" --output-dir='./crabnlp'

done
# conda run -n jupyter jupyter nbconvert --to python "bot.ipynb"
# conda run -n jupyter jupyter nbconvert --to python "commons.ipynb"
# conda run -n jupyter jupyter nbconvert --to python "summarize.ipynb"
# conda run -n jupyter jupyter nbconvert --to python "clusterize.ipynb"
# conda run -n jupyter jupyter nbconvert --to python "youtube.ipynb"
# conda run -n jupyter jupyter nbconvert --to python "whisperapi.ipynb"