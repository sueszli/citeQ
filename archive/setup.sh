cd ~
git clone https://github.com/sueszli/citeQ.git
cd citeQ/
git checkout experinment
sudo apt-get install -y pciutils
curl https://ollama.ai/install.sh | sh

#open terminal serve ollama
ollama serve

#back to first terminal
ollama pull llama2
pip install gdown
gdown 1xYasfiWA3aeXT-pb-MlFLEpbnEyM9lbq
mv citeQ_waterloo_profs.db citeQ.db

pip install thefuzz
pip install PyPDF2
pip install sqlalchemy
pip install backoff
pip install python-dotenv
pip install rich
pip install langchain

python citeq -c --start 559000 --end 697609