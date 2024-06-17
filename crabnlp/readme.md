# Workflow
Some files in `crabnlp` folder are generated from related ipynb files from `notebooks` folder. Every file in `notebooks` folder that doesn't start with three digits is being translated to plain `.py` file with `build.sh` file.

So don't edit `crabnlp/*.py` file if it contains `# In[ ]:` like lines. Instead edit corresponding notebook and then build.