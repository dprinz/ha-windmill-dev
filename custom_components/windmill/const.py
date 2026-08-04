"""Constants for the Windmill integration."""

DOMAIN = "windmill"

CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"
CONF_WORKSPACE = "workspace"

DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_REQUEST_TIMEOUT = 30.0
MAX_RESPONSE_BYTES = 65_536

OPT_INSTANCE_HEALTH = "instance_health"
OPT_DETAILED_HEALTH = "detailed_health"
OPT_WORKER_GROUPS = "worker_groups"
OPT_WORKER_DETAILS = "worker_details"
OPT_RUN_OBSERVATION = "run_observation"
OPT_UPDATE_ENTITY = "update_entity"
OPT_RUNNABLES = "runnables"
OPT_RUNNABLE_BUTTONS = "runnable_buttons"
OPT_RUNNABLE_DETAILS = "runnable_details"
OPT_RUN_SCOPE = "run_scope"

RUN_SCOPE_ALL = "all"
RUN_SCOPE_SELECTED = "selected_runnables"
RUN_SCOPE_STARTED = "home_assistant_started"
RUN_SCOPES = (RUN_SCOPE_ALL, RUN_SCOPE_SELECTED, RUN_SCOPE_STARTED)
# Observing everything the token may see is the previous behavior and needs no other option.
DEFAULT_RUN_SCOPE = RUN_SCOPE_ALL

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_KIND = "kind"
ATTR_PATH = "path"
ATTR_ARGUMENTS = "arguments"
ATTR_JOB_ID = "job_id"

MAX_TRACKED_JOBS = 50
TRACKED_JOB_TTL_HOURS = 24

MAX_SELECTED_RUNNABLES = 25

# Windmill asked us to slow down: poll no faster than this until one refresh succeeds again.
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 300.0
MAX_RATE_LIMIT_BACKOFF_SECONDS = 900.0

# A rolling worker upgrade runs two versions for a while; only sustained drift is actionable.
WORKER_DRIFT_GRACE_MINUTES = 30

FEATURE_OPTIONS = (
    OPT_INSTANCE_HEALTH,
    OPT_DETAILED_HEALTH,
    OPT_WORKER_GROUPS,
    OPT_WORKER_DETAILS,
    OPT_RUN_OBSERVATION,
    OPT_UPDATE_ENTITY,
    OPT_RUNNABLE_BUTTONS,
    OPT_RUNNABLE_DETAILS,
)

# Administrative and high-cardinality features stay disabled until a user opts in.
FEATURE_DEFAULTS = {
    OPT_INSTANCE_HEALTH: True,
    OPT_DETAILED_HEALTH: False,
    OPT_WORKER_GROUPS: False,
    OPT_WORKER_DETAILS: False,
    OPT_RUN_OBSERVATION: True,
    OPT_UPDATE_ENTITY: False,
    OPT_RUNNABLE_BUTTONS: False,
    OPT_RUNNABLE_DETAILS: False,
}
