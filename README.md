Prerequisites:
- Install poetry (with brew or otherwise)
  - `brew install poetry`
- Ensure Python 3.12 

Installation:

1. Create a folder for hosting your workspace
   `mkdir ws-autobots`
2. Git clone all autobot repos
   - `git clone https://github.com/Pratishthan/autobots-devtools-shared-lib.git`
   - `git clone https://github.com/Pratishthan/autobots-agents-bro.git`
3. Install repos
```shell
cd /work/src/ws-autobots || exit 1 # check the path
python3.12 -m venv .venv # only 3.12 
poetry config virtualenvs.path "$(pwd)" --local
poetry config virtualenvs.in-project false --local
# Repo 1
cd autobots-devtools-shared-lib
poetry lock
poetry install
# Repo 2
cd autobots-agents-bro
poetry lock
poetry install
```
4. Prepare .env 