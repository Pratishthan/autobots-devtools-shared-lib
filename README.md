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

export WORKSPACE_DIR=/work/src/ws-autobots
cd $WORKSPACE_DIR || exit 1
python3.12 -m venv .venv
poetry config virtualenvs.path "$(pwd)" --local
poetry config virtualenvs.in-project false --local
source .venv/bin/activate

# Repo 1

cd $WORKSPACE_DIR/autobots-devtools-shared-lib
poetry lock
poetry install
poetry run pre-commit --version
poetry run pre-commit install
cd $WORKSPACE_DIR

# Repo 2

cd autobots-agents-bro
poetry lock
poetry install
poetry run pre-commit --version
poetry run pre-commit install
cd $WORKSPACE_DIR

4. Prepare .env
