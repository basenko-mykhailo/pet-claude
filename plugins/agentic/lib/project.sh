# Locate and load the project config. Sourced by every libexec/ script of the plugin.
#
# The project directory is $AGENTIC_PROJECT (exported by the pipeline, so agents'
# commands inherit it) or <git root>/.claude/agentic when run by hand from the repo.
# Defines: AGENTIC_DIR, BIN (the plugin's libexec/), REPO, PROJECT_DIR, PROJECT_BIN, EPIC, + the config.

AGENTIC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BIN="$AGENTIC_DIR/libexec"

if [[ -z ${AGENTIC_PROJECT:-} ]]; then
  AGENTIC_PROJECT="$(git rev-parse --show-toplevel 2>/dev/null)/.claude/agentic"
fi
PROJECT_DIR=$(cd "$AGENTIC_PROJECT" 2>/dev/null && pwd) \
  || { echo "agentic: no project config at $AGENTIC_PROJECT (create .claude/agentic/config.sh)" >&2; exit 2; }
PROJECT_BIN="$PROJECT_DIR/bin"
# The main checkout is the repo that holds the project dir (not the worktree).
REPO=$(git -C "$PROJECT_DIR" rev-parse --show-toplevel)
EPIC=${EPIC:-0}
export AGENTIC_PROJECT="$PROJECT_DIR"

[[ -f $PROJECT_DIR/config.sh ]] || { echo "agentic: missing $PROJECT_DIR/config.sh" >&2; exit 2; }
# shellcheck source=/dev/null
source "$PROJECT_DIR/config.sh"
