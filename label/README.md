# install dependencies

python3 -m venv env

source env/bin/activate

pip install openai==0.27.8

# run

python label.py '<API KEY>' 'PATH to the jsonl file'

# sample input test.jsonl; sample output test1.jsonl
