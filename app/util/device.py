import hashlib
from typing import Dict, Optional


def generate_fingerprint(device_info: Dict) -> str:
    """Gera fingerprint único do dispositivo"""
    # Combinar informações únicas do device
    unique_string = f"{device_info.get('device_id', '')}"
    unique_string += f"{device_info.get('platform', '')}"
    unique_string += f"{device_info.get('model', '')}"

    # Gerar hash
    return hashlib.sha256(unique_string.encode()).hexdigest()


def parse_user_agent(user_agent: str) -> Dict:
    """Parse User-Agent header"""
    # Implementação simplificada
    platform = "unknown"
    if "Android" in user_agent:
        platform = "android"
    elif "iPhone" in user_agent:
        platform = "ios"
    elif "Windows" in user_agent:
        platform = "windows"
    elif "Mac" in user_agent:
        platform = "mac"
    elif "Linux" in user_agent:
        platform = "linux"

    return {"platform": platform}