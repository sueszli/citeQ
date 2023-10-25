```
            88                        ,ad8888ba,
            ""    ,d                 d8"'    `"8b
                  88                d8'        `8b
 ,adPPYba,  88  MM88MMM  ,adPPYba,  88          88
a8"     ""  88    88    a8P_____88  88          88
8b          88    88    8PP"""""""  Y8,    "88,,8P
"8a,   ,aa  88    88,   "8b,   ,aa   Y8a.    Y88P
 `"Ybbd8"'  88    "Y888  `"Ybbd8"'    `"Y8888Y"Y8a
```

<br>

installation:

```bash
# clone
git clone https://github.com/sueszli/citeQ.git
cd citeQ

# install dependencies
if command -v python3 &>/dev/null; then echo "found python3 install"; else echo "please install python3 first"; fi
python3 -m pip install --upgrade pip > /dev/null
pip3 install pipreqs > /dev/null
rm -rf requirements.txt > /dev/null
pipreqs . > /dev/null
pip3 install -r requirements.txt > /dev/null

# run
python3 citeq --help

# example usage
python3 citeq jimmy lin -i university of waterloo
```
