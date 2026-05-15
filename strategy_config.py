import os
import json
import logging

logger = logging.getLogger(__name__)

STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), "strategies")
DEFAULT_PROFILE = "balanced"

def list_strategy_profiles() -> list[str]:
    """Lista los nombres de perfiles disponibles en el directorio strategies/."""
    if not os.path.exists(STRATEGIES_DIR):
        return [DEFAULT_PROFILE]
    
    profiles = []
    for f in os.listdir(STRATEGIES_DIR):
        if f.endswith(".json"):
            profiles.append(f[:-5])
    
    return sorted(profiles) if profiles else [DEFAULT_PROFILE]

def get_default_strategy_profile() -> str:
    """Devuelve el nombre del perfil por defecto."""
    return DEFAULT_PROFILE

def load_strategy_profile(profile_name: str | None = None) -> dict:
    """Carga un perfil de estrategia desde un archivo JSON."""
    name = profile_name or DEFAULT_PROFILE
    file_path = os.path.join(STRATEGIES_DIR, f"{name}.json")
    
    if not os.path.exists(file_path):
        if name == DEFAULT_PROFILE:
            # Fallback hardcoded si incluso el balanced.json no existe
            logger.warning(f"Default profile {name}.json not found. Using fallback hardcoded config.")
            return _get_fallback_balanced_config()
        else:
            raise FileNotFoundError(f"Perfil de estrategia no encontrado: {name} (buscado en {file_path})")
            
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        is_valid, errors = validate_strategy_config(config)
        if not is_valid:
            logger.warning(f"Configuración de {name} tiene errores: {', '.join(errors)}")
            
        return config
    except Exception as e:
        logger.error(f"Error cargando perfil {name}: {e}")
        if name == DEFAULT_PROFILE:
            return _get_fallback_balanced_config()
        raise

def validate_strategy_config(config: dict) -> tuple[bool, list[str]]:
    """Valida que la configuración tenga los campos necesarios y valores razonables."""
    errors = []
    required_fields = [
        "min_score_enter", "min_score_watchlist", "rsi_overbought", "rsi_oversold",
        "atr_stop_loss_mult", "atr_take_profit_mult", "risk_reward_min"
    ]
    
    for field in required_fields:
        if field not in config:
            errors.append(f"Campo faltante: {field}")
            
    # Validaciones de rangos
    if "min_score_enter" in config:
        if not (0 <= config["min_score_enter"] <= 10):
            errors.append("min_score_enter debe estar entre 0 y 10")
            
    if "atr_stop_loss_mult" in config and config["atr_stop_loss_mult"] <= 0:
        errors.append("atr_stop_loss_mult debe ser positivo")
        
    if "risk_reward_min" in config and config["risk_reward_min"] <= 0:
        errors.append("risk_reward_min debe ser mayor a 0")
        
    return len(errors) == 0, errors

def _get_fallback_balanced_config() -> dict:
    return {
        "name": "balanced",
        "description": "Fallback balanced config (hardcoded).",
        "min_score_enter": 7.0,
        "min_score_watchlist": 5.5,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "atr_stop_loss_mult": 1.5,
        "atr_take_profit_mult": 2.5,
        "min_volume_factor": 1.0,
        "near_resistance_penalty": 1.0,
        "near_support_bonus": 0.5,
        "btc_regime_weight": 1.0,
        "trend_weight": 1.0,
        "momentum_weight": 1.0,
        "volume_weight": 1.0,
        "risk_reward_min": 1.5,
        "max_leverage_warning": 3
    }

def get_strategy_meta(profile_name: str | None = None) -> dict:
    """Retorna metadatos básicos del perfil de estrategia para trazabilidad."""
    name = profile_name or DEFAULT_PROFILE
    # En el futuro podramos leer la versin desde el JSON
    return {
        "strategy_profile": name,
        "strategy_version": "1.0.0"
    }
