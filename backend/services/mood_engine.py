from config import MOOD as MC, GAME as GC


def derive_mood(suspicion: float, intent_category: str | None = None, delta: float = 0.0) -> str:
    """
    Map suspicion level to mood string.
    Generous thresholds — player stays in warm/impressed most of the time.
    """
    # Reach "impressed" on rapport intent with low suspicion
    if intent_category == "rapport" and suspicion < MC.IMPRESSED_CAP:
        return "impressed"

    if suspicion < MC.WARM_MAX:
        return "warm"
    elif suspicion < MC.NEUTRAL_MAX:
        return "neutral"
    elif suspicion < MC.SUSPICIOUS_MAX:
        return "suspicious"
    else:
        return "hostile"


def is_game_over_suspicion(suspicion: float) -> bool:
    return suspicion >= GC.GAME_OVER_SUSPICION
