PALETTE = ["#FF6FA5", "#2AA9E0", "#9B6BFF", "#FFB627", "#4CB944", "#FF5A45"]


def color_for(seed: str) -> str:
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return PALETTE[h % len(PALETTE)]
