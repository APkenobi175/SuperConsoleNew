## This script is used to run the launcher using poetry.
# Run this script instead of launching the launcher directly so we can make sure we are in the proper virtual environment.

set -euo pipefail
poetry run python -m launcher.main

chmod +x scripts/run.sh
./scripts/run.sh

# End of script