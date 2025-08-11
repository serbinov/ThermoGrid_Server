# file: utils.py

def format_uptime(ms):
    """Конвертирует миллисекунды в строку 'Дни ч:м:с'."""
    if not isinstance(ms, (int, float)) or ms < 0:
        return "N/A"
    
    seconds = int(ms / 1000)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    else:
        return f"{hours}ч {minutes}м {seconds}с"