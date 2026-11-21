"""ICE RIOT team table (original teams). Colors are sRGB hex; teams.json gets linear RGB."""

TEAMS = [
    dict(id="NAR", city="NORTHPORT", name="NARWHALS", primary="#00A6A6", secondary="#0B2545", trim="#FFFFFF"),
    dict(id="INF", city="BRIMSTONE", name="INFERNO", primary="#C8102E", secondary="#FF6B12", trim="#121212"),
    dict(id="YET", city="GLACIER BAY", name="YETIS", primary="#79C7F2", secondary="#F4F8FB", trim="#A9B4C0"),
    dict(id="HAM", city="STEEL VALLEY", name="HAMMERS", primary="#17181B", secondary="#F2B705", trim="#FFFFFF"),
    dict(id="BRW", city="BAYOU", name="BRAWLERS", primary="#3E7B27", secondary="#E3B22B", trim="#111111"),
    dict(id="VIP", city="NEON COAST", name="VIPERS", primary="#E6007E", secondary="#7B2CFF", trim="#FFFFFF"),
    dict(id="GRZ", city="TIMBER RIDGE", name="GRIZZLIES", primary="#6B3D1F", secondary="#F27F1B", trim="#F3E5C4"),
    dict(id="COM", city="ROCKET CITY", name="COMETS", primary="#1F4FD8", secondary="#E0182D", trim="#FFFFFF"),
]

BY_ID = {t["id"]: t for t in TEAMS}

# Default home/away for the preview renders
HOME = "NAR"
AWAY = "INF"

# Referee palette
REF = dict(jersey="#F2F2F2", stripe="#111111", trim="#E0182D")
