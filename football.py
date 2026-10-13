"""
Fonctions utilitaires pour les prévisions (Poisson) et le calcul des buts moyens.
Ce module est séparé pour faciliter les tests unitaires.
"""

import math


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def forecast(h, a):
    vals = [(i, j, pois(i, h) * pois(j, a)) for i in range(16) for j in range(16)]
    vals.sort(key=lambda x: x[2], reverse=True)
    top3 = vals[:3]
    btts = (1 - math.exp(-h)) * (1 - math.exp(-a))
    over = 1 - sum(pois(k, h + a) for k in range(3))
    return top3, btts, over


def avg_goals(matches, team_id, side):
    vals = []
    for m in matches:
        if m.get("fixture", {}).get("status", {}).get("short") not in ("FT", "AET", "PEN"):
            continue
        t = m.get("teams", {})
        if t.get(side, {}).get("id") != team_id:
            continue
        g = m.get("goals", {})
        if g.get("home") is None or g.get("away") is None:
            continue
        vals.append((g["home"], g["away"]) if side == "home" else (g["away"], g["home"]))
    return vals
