# install dependencies

python3 -m venv env

source env/bin/activate

pip install openai==0.27.8

# run

python label.py '<API KEY>' 'PATH to the jsonl file'

# sample input test.jsonl; sample output test1.jsonl

# the LClabel
it will label the original dataset with the mistral model

to run it, firt enable the mistral model by the command: ollama run mistral

Then, we can run the LClabel.py with the target data file.
for example:

python LClabel.py '/home/g83wang/Documents/cs848/scicite/test1.jsonl'

The data file shall have entries in the format:
{"source": "explicit", "citeEnd": 175, "sectionName": "Introduction", "citeStart": 168, "string": "However, how frataxin interacts with the Fe-S cluster biosynthesis components remains unclear as direct one-to-one interactions with each component were reported (IscS [12,22], IscU/Isu1 [6,11,16] or ISD11/Isd11 [14,15]).", "label": "background", "label_confidence": 1.0, "citingPaperId": "1872080baa7d30ec8fb87be9a65358cd3a7fb649", "citedPaperId": "894be9b4ea46a5c422e81ef3c241072d4c73fdc0", "isKeyCitation": true, "id": "1872080baa7d30ec8fb87be9a65358cd3a7fb649>894be9b4ea46a5c422e81ef3c241072d4c73fdc0", "unique_id": "1872080baa7d30ec8fb87be9a65358cd3a7fb649>894be9b4ea46a5c422e81ef3c241072d4c73fdc0_11", "excerpt_index": 11}
