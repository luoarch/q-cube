"""Agent strategy profiles — hard rejects, soft preferences, core metrics."""

from q3_ai_assistant.council.profiles.barsi_profile import BARSI_PROFILE
from q3_ai_assistant.council.profiles.buffett_profile import BUFFETT_PROFILE
from q3_ai_assistant.council.profiles.graham_profile import GRAHAM_PROFILE
from q3_ai_assistant.council.profiles.greenblatt_profile import GREENBLATT_PROFILE

ALL_PROFILES = {
    "barsi": BARSI_PROFILE,
    "graham": GRAHAM_PROFILE,
    "greenblatt": GREENBLATT_PROFILE,
    "buffett": BUFFETT_PROFILE,
}
