import re

def extract_keywords(text):
    """Extract meaningful keywords from text (lowercase, no short/stop words)."""
    stop_words = {
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "do", "does", "did", "has", "have", "had", "will", "would", "can",
        "could", "should", "may", "might", "to", "of", "in", "on", "at",
        "for", "with", "and", "or", "but", "not", "so", "if", "then",
        "this", "that", "what", "which", "who", "how", "when", "where",
        "why", "all", "each", "every", "any", "no", "yes", "ok", "hi",
        "hello", "hey", "please", "thanks", "thank", "from", "by", "up",
        "about", "into", "just", "also", "than", "very", "too", "here",
        "kya", "hai", "ka", "ki", "ke", "ko", "se", "me", "ye", "wo",
        "toh", "bhi", "aur", "par", "nahi", "na", "ho", "haan", "ji",
        "bhai", "sir", "mam", "mujhe", "mera", "tera", "uska"
    }
    words = re.findall(r'[a-zA-Z0-9\u0900-\u097F]+', text.lower())
    return [w for w in words if len(w) > 1 and w not in stop_words]

def format_countdown(seconds):
    """Format seconds into a readable countdown string."""
    if seconds <= 0: return "Starting now!"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if mins > 0: parts.append(f"{mins}m")
    return " ".join(parts) if parts else "< 1m"
