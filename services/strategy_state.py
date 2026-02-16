from models.session import SessionState


STRATEGY_NEUTRAL = "Neutral"
STRATEGY_SUSPICIOUS = "Suspicious"
STRATEGY_EXTRACTION_MODE = "Extraction Mode"
STRATEGY_HIGH_CONFIDENCE = "High Confidence Scam"
STRATEGY_HARVEST_MODE = "Intelligence Harvest Mode"


def infer_strategy_state(
    state: SessionState,
    rolling_score: float | None = None,
    scam_detected: bool | None = None,
    actionable_count: int | None = None,
    agent_turns: int | None = None,
) -> str:
    score = float(state.rolling_scam_score if rolling_score is None else rolling_score)
    actionable = state.intel.actionable_category_count() if actionable_count is None else actionable_count
    detected = state.scam_detected if scam_detected is None else scam_detected
    turns = state.agent_turns if agent_turns is None else agent_turns

    if score < 3.0 and not detected:
        return STRATEGY_NEUTRAL
    if score < 6.0 and not detected:
        return STRATEGY_SUSPICIOUS
    if score < 10.0:
        return STRATEGY_EXTRACTION_MODE
    if actionable >= 3 or turns >= 5:
        return STRATEGY_HARVEST_MODE
    return STRATEGY_HIGH_CONFIDENCE
