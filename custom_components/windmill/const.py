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

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_KIND = "kind"
ATTR_PATH = "path"
ATTR_ARGUMENTS = "arguments"
ATTR_JOB_ID = "job_id"

MAX_TRACKED_JOBS = 50
TRACKED_JOB_TTL_HOURS = 24

MAX_SELECTED_RUNNABLES = 25

FEATURE_OPTIONS = (
    OPT_INSTANCE_HEALTH,
    OPT_DETAILED_HEALTH,
    OPT_WORKER_GROUPS,
    OPT_WORKER_DETAILS,
    OPT_RUN_OBSERVATION,
    OPT_UPDATE_ENTITY,
    OPT_RUNNABLE_BUTTONS,
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
}
