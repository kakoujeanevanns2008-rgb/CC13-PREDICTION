#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CC13 Prédiction - bot quotidien (ESPN -> Groq -> 1xBet -> Supabase)"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def secret(nom, defaut):
    v = os.environ.get(nom, "").strip()
    return v if v else defaut


# ====================== TES CLES ET LIENS ======================
GROQ_KEY = secret("GROQ_KEY", "COLLE_ICI_TA_CLE_GROQ")
SUPABASE_URL = secret("SUPABASE_URL", "https://VOTRE-PROJET.supabase.co")
SUPABASE_KEY = secret("SUPABASE_KEY", "COLLE_ICI_LA_CLE_SERVICE_ROLE")
MON_CODE_PROMO = secret("MON_CODE_PROMO", "MON_CODE_PROMO")
MON_LIEN_INSCRIPTION = secret("MON_LIEN_INSCRIPTION", "https://1xbet.ci")
MON_LIEN_TELEGRAM = secret("MON_LIEN_TELEGRAM", "https://t.me/VOTRE_CHAINE")
# ===============================================================

ESPN = "https://site.api.espn.com/apis"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
BASE_1XBET = "https://1xbet.ci"
FUSEAU = ZoneInfo("Africa/Abidjan")
MAX_MATCHES = 3
DOSSIER_CAPTURES = "screenshots"

# Championnats par ordre de priorité (code ESPN, nom affiché)
LIGUES = [
    ("uefa.champions", "Ligue des champions"),
    ("uefa.europa", "Ligue Europa"),
    ("uefa.europa.conf", "Ligue Conférence"),
    ("caf.champions", "Ligue des champions CAF"),
    ("eng.1", "Premier League"),
    ("esp.1", "LaLiga"),
    ("ita.1", "Serie A"),
    ("ger.1", "Bundesliga"),
    ("fra.1", "Ligue 1"),
    ("por.1", "Liga Portugal"),
    ("ned.1", "Eredivisie"),
    ("eng.2", "Championship"),
    ("usa.1", "MLS"),
]

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

MARCHES = {
    "V1": (r"^(1X2|R[ée]sultat)", r"^1\d+[.,]\d+$"),
    "N": (r"^(1X2|R[ée]sultat)", r"^[XN]\d+[.,]\d+$"),
    "V2": (r"^(1X2|R[ée]sultat)", r"^2\d+[.,]\d+$"),
    "1N": (r"double chance", r"^(1X|1N)\d+[.,]\d+$"),
    "N2": (r"double chance", r"^(X2|N2)\d+[.,]\d+$"),
    "Plus 2.5": (r"^totals?$|^total\b", r"(plus|over)\D{0,6}2[.,]5\D{0,3}\d+[.,]\d+$"),
    "Moins 2.5": (r"^totals?$|^total\b", r"(moins|under)\D{0,6}2[.,]5\D{0,3}\d+[.,]\d+$"),
    "BTTS": (r"deux [ée]quipes marquent|both teams to score", r"^(oui|yes)\d+[.,]\d+$"),
}

LIBELLES = {
    "V1": "V1 - Victoire de {dom}",
    "N": "N - Match nul",
    "V2": "V2 - Victoire de {ext}",
    "1N": "1N - {dom} ne perd pas",
    "N2": "N2 - {ext} ne perd pas",
    "Plus 2.5": "Plus de 2,5 buts",
    "Moins 2.5": "Moins de 2,5 buts",
    "BTTS": "Les deux équipes marquent",
}


# ----------------------------- HTTP -----------------------------
def http_json(url, methode="GET", entetes=None, corps=None, timeout=60):
    h = {"User-Agent": "Mozilla/5.0 (compatible; CC13Bot/1.0)", "Accept": "application/json"}
    if entetes:
        h.update(entetes)
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=donnees, headers=h, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read().decode("utf-8")
            return json.loads(brut) if brut.strip() else {}
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {url[:90]} -> {e.read().decode('utf-8', 'ignore')[:200]}")
        raise


# ------------------------------ ESPN ------------------------------
def lire_equipe(comp, cote):
    for c in comp.get("competitors", []):
        if c.get("homeAway") == cote:
            t = c.get("team", {})
            return {
                "id": str(t.get("id", "")),
                "nom": t.get("displayName") or t.get("name") or "?",
                "form": c.get("form") or "",
            }
    return None


def choisir_matchs(date_jour):
    date_espn = date_jour.replace("-", "")
    trouves = []
    for rang, (slug, nom_ligue) in enumerate(LIGUES):
        url = f"{ESPN}/site/v2/sports/soccer/{slug}/scoreboard?dates={date_espn}"
        try:
            data = http_json(url, timeout=30)
        except Exception:
            continue
        for ev in data.get("events", []):
            try:
                comp = ev["competitions"][0]
                etat = comp.get("status", {}).get("type", {}).get("state") or \
                    ev.get("status", {}).get("type", {}).get("state")
                if etat != "pre":
                    continue
                dom = lire_equipe(comp, "home")
                ext = lire_equipe(comp, "away")
                if not dom or not ext:
                    continue
                trouves.append({
                    "id": str(ev["id"]),
                    "slug": slug,
                    "ligue": nom_ligue,
                    "date": ev.get("date") or comp.get("date"),
                    "dom": dom,
                    "ext": ext,
                    "rang": rang,
                })
            except Exception as e:
                print("[ESPN] match ignoré :", e)
    print(f"{len(trouves)} matchs à venir trouvés pour {date_jour}")
    trouves.sort(key=lambda m: (m["rang"], m["date"] or ""))
    return trouves[:MAX_MATCHES]


_cache_classements = {}


def classement_ligue(slug):
    if slug in _cache_classements:
        return _cache_classements[slug]
    resultat = {}
    try:
        rep = http_json(f"{ESPN}/v2/sports/soccer/{slug}/standings", timeout=30)
        groupes = rep.get("children") or [rep]
        for g in groupes:
            for e in g.get("standings", {}).get("entries", []):
                st = {s.get("name"): s.get("value") for s in e.get("stats", [])}
                tid = str(e.get("team", {}).get("id", ""))
                try:
                    resultat[tid] = (
                        f'{int(st["rank"])}e - {int(st["points"])} pts - {int(st["gamesPlayed"])} J '
                        f'({int(st["wins"])}V {int(st["ties"])}N {int(st["losses"])}D)'
                    )
                except Exception:
                    pass
    except Exception as e:
        print("[classement] indisponible :", e)
    _cache_classements[slug] = resultat
    return resultat


def convertir_forme(f):
    if not f:
        return "N/D"
    table = {"W": "V", "D": "N", "L": "D"}
    lettres = [table[c] for c in f.upper() if c in table][-5:]
    return " ".join(lettres) if lettres else "N/D"


def pourcent(v):
    try:
        return f"{float(v):.0f}%"
    except Exception:
        return None


def construire_stats(m):
    dom, ext = m["dom"], m["ext"]
    stats = {
        "forme_domicile": convertir_forme(dom["form"]),
        "forme_exterieur": convertir_forme(ext["form"]),
        "h2h": [],
        "classement_domicile": "N/D",
        "classement_exterieur": "N/D",
        "probas": {},
        "conseil_api": "",
    }

    classement = classement_ligue(m["slug"])
    stats["classement_domicile"] = classement.get(dom["id"], "N/D")
    stats["classement_exterieur"] = classement.get(ext["id"], "N/D")

    try:
        rep = http_json(f"{ESPN}/site/v2/sports/soccer/{m['slug']}/summary?event={m['id']}", timeout=30)
    except Exception as e:
        print("[summary] indisponible :", e)
        return stats

    noms = {dom["id"]: dom["nom"], ext["id"]: ext["nom"]}
    try:
        blocs = rep.get("headToHeadGames") or []
        if blocs:
            for ev in (blocs[0].get("events") or [])[:5]:
                nom_d = noms.get(str(ev.get("homeTeamId")), "?")
                nom_e = noms.get(str(ev.get("awayTeamId")), "?")
                stats["h2h"].append({
                    "date": str(ev.get("gameDate", ""))[:10],
                    "match": f"{nom_d} - {nom_e}",
                    "score": f'{ev.get("homeTeamScore", "?")}-{ev.get("awayTeamScore", "?")}',
                })
    except Exception as e:
        print("[h2h] ignoré :", e)

    try:
        pr = rep.get("predictor") or {}
        pd = pourcent(pr["homeTeam"]["gameProjection"])
        pe = pourcent(pr["awayTeam"]["gameProjection"])
        if pd and pe:
            nul = max(0, 100 - float(pr["homeTeam"]["gameProjection"]) - float(pr["awayTeam"]["gameProjection"]))
            stats["probas"] = {"domicile": pd, "nul": f"{nul:.0f}%", "exterieur": pe}
    except Exception:
        pass
    return stats


# ------------------------------ GROQ ------------------------------
def analyser_avec_groq(m, stats):
    dom = m["dom"]["nom"]
    ext = m["ext"]["nom"]
    choix = ", ".join(MARCHES.keys())
    consigne = (
        "Tu es un analyste de pronostics football. Réponds UNIQUEMENT avec un objet JSON "
        'de la forme {"analyse": "...", "pronostic": "...", "confiance": 65}. '
        "Règles : 'analyse' = exactement 3 phrases en français, basées sur les statistiques fournies, "
        "sans inventer de données (si une statistique vaut N/D, ne l'invente pas). "
        f"'pronostic' = une seule valeur parmi : {choix}. "
        "'confiance' = entier entre 50 et 85 (prudence : ne dépasse jamais 85)."
    )
    contenu = {
        "match": f"{dom} (domicile) vs {ext} (extérieur)",
        "competition": m["ligue"],
        "statistiques": stats,
    }
    corps = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": consigne},
            {"role": "user", "content": json.dumps(contenu, ensure_ascii=False)},
        ],
        "temperature": 0.4,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }
    rep = http_json(GROQ_URL, "POST", {"Authorization": f"Bearer {GROQ_KEY}"}, corps)
    sortie = json.loads(rep["choices"][0]["message"]["content"])

    pronostic = str(sortie.get("pronostic", "")).strip()
    if pronostic not in MARCHES:
        pronostic = "1N"
    try:
        confiance = int(sortie.get("confiance", 60))
    except Exception:
        confiance = 60
    confiance = max(50, min(85, confiance))
    analyse = str(sortie.get("analyse", "")).strip() or "Analyse indisponible."
    return analyse, pronostic, confiance


# ----------------------------- 1XBET ------------------------------
JS_LIENS = r"""
return Array.from(document.querySelectorAll('a[href*="/line/football/"]')).map(a => a.href);
"""

JS_CLIC_TEXTE = r"""
const re = new RegExp(arguments[0], 'i');
let best = null, bestLen = 1e9;
for (const el of document.querySelectorAll('button,a,div,span,li,p')) {
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) continue;
  const t = (el.innerText || '').trim().replace(/\s+/g, ' ');
  if (t.length === 0 || t.length > 60) continue;
  if (re.test(t) && t.length < bestLen) { best = el; bestLen = t.length; }
}
if (!best) return false;
best.scrollIntoView({block: 'center'});
best.click();
return true;
"""

JS_CLIC_PARI = r"""
const marche = new RegExp(arguments[0], 'i');
const issue = new RegExp(arguments[1], 'i');
const titres = Array.from(document.querySelectorAll('div,span,p,h2,h3,h4,li,button')).filter(e => {
  const t = (e.innerText || '').trim();
  return t.length > 0 && t.length < 50 && e.children.length <= 1 &&
         marche.test(t) && e.getBoundingClientRect().height > 0;
});
for (const titre of titres) {
  let boite = titre;
  for (let i = 0; i < 6 && boite.parentElement; i++) {
    boite = boite.parentElement;
    const cands = Array.from(boite.querySelectorAll('div,span,button,li,a')).filter(e => {
      const t = (e.innerText || '').trim().replace(/\s+/g, '');
      return t.length > 0 && t.length < 30 && /\d+[.,]\d{2}/.test(t) &&
             issue.test(t) && e.getBoundingClientRect().height > 0;
    });
    if (cands.length) {
      cands.sort((a, b) => a.innerText.length - b.innerText.length);
      cands[0].scrollIntoView({block: 'center'});
      cands[0].click();
      return (cands[0].innerText || '').trim();
    }
  }
}
return null;
"""

JS_LIRE_CODE = r"""
const ok = t => /^[A-Z0-9]{5,8}$/.test(t) && /\d/.test(t) && /[A-Z]/.test(t);
for (const e of document.querySelectorAll('*')) {
  if (e.children.length !== 0 || e.getBoundingClientRect().height === 0) continue;
  const t = (e.innerText || e.textContent || '').trim();
  if (ok(t)) return t;
}
for (const i of document.querySelectorAll('input')) {
  const v = (i.value || '').trim();
  if (ok(v)) return v;
}
return null;
"""


def normaliser(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def mots_cles(nom):
    stop = {"fc", "cf", "sc", "ac", "as", "afc", "club", "de", "del", "la", "le", "the", "and"}
    return [m for m in normaliser(nom).split() if len(m) >= 3 and m not in stop]


def pause(s):
    time.sleep(s)


def capture(driver, nom):
    try:
        os.makedirs(DOSSIER_CAPTURES, exist_ok=True)
        driver.save_screenshot(os.path.join(DOSSIER_CAPTURES, f"{nom}.png"))
    except Exception:
        pass


def creer_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=fr-FR")
    opts.add_argument("--window-size=390,844")
    opts.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 3.0},
        "userAgent": IPHONE_UA,
    })
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver


def fermer_popups(driver):
    for motif in (r"^(ok|accepter|j'accepte|fermer|continuer|plus tard|non merci)$",):
        try:
            driver.execute_script(JS_CLIC_TEXTE, motif)
        except Exception:
            pass


def trouver_lien_match(driver, dom, ext):
    mots_dom, mots_ext = mots_cles(dom), mots_cles(ext)
    for _ in range(12):
        for href in driver.execute_script(JS_LIENS) or []:
            slug = normaliser(href.split("/line/football/")[-1])
            if any(m in slug for m in mots_dom) and any(m in slug for m in mots_ext):
                return href
        driver.execute_script("window.scrollBy(0, 1500);")
        pause(1.5)
    return None


def recuperer_coupon(dom, ext, code_pari, etiquette):
    driver = None
    try:
        driver = creer_driver()
        driver.get(f"{BASE_1XBET}/fr/line/football")
        pause(7)
        fermer_popups(driver)
        capture(driver, f"{etiquette}_1_liste")

        lien = trouver_lien_match(driver, dom, ext)
        if not lien:
            print(f"[1xBet] match introuvable : {dom} - {ext}")
            capture(driver, f"{etiquette}_2_introuvable")
            return None

        driver.get(lien)
        pause(7)
        fermer_popups(driver)
        marche, issue = MARCHES[code_pari]
        clic = driver.execute_script(JS_CLIC_PARI, marche, issue)
        capture(driver, f"{etiquette}_3_pari")
        if not clic:
            print(f"[1xBet] pari '{code_pari}' introuvable sur la page du match")
            return None
        pause(2)

        for _ in range(4):
            if driver.execute_script(JS_CLIC_TEXTE, r"^(enregistrer|sauvegarder)( le coupon)?$"):
                pause(3)
                capture(driver, f"{etiquette}_4_apres_enregistrer")
                code = driver.execute_script(JS_LIRE_CODE)
                if code:
                    return code
            else:
                driver.execute_script(JS_CLIC_TEXTE, r"^(\d+\s*)?(coupon|mon coupon|voir le coupon)$")
                pause(2)
        capture(driver, f"{etiquette}_5_echec")
        return None
    except Exception as e:
        print("[1xBet] erreur :", e)
        if driver:
            capture(driver, f"{etiquette}_erreur")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------- SUPABASE ----------------------------
def envoyer_supabase(ligne):
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/pronostics?on_conflict=fixture_id"
    entetes = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    http_json(url, "POST", entetes, [ligne])


# ------------------------------ MAIN ------------------------------
def main():
    date_jour = datetime.now(FUSEAU).strftime("%Y-%m-%d")
    print("=== CC13 Prédiction -", date_jour, "===")
    matchs = choisir_matchs(date_jour)
    if not matchs:
        print("Aucun match exploitable aujourd'hui.")
        return 0

    for i, m in enumerate(matchs, start=1):
        dom = m["dom"]["nom"]
        ext = m["ext"]["nom"]
        print(f"\n--- Match {i} : {dom} - {ext} ({m['ligue']}) ---")
        try:
            stats = construire_stats(m)
            analyse, code_pari, confiance = analyser_avec_groq(m, stats)
        except Exception as e:
            print("[IA/stats] échec, match ignoré :", e)
            continue
        print(f"Pronostic : {code_pari} ({confiance}%)")

        coupon = recuperer_coupon(dom, ext, code_pari, f"match{i}")
        print("Code coupon :", coupon or "indisponible")

        ligne = {
            "fixture_id": int(m["id"]),
            "date_match": date_jour,
            "league": m["ligue"],
            "home_team": dom,
            "away_team": ext,
            "match_name": f"{dom} - {ext}",
            "kickoff": m["date"],
            "prediction": LIBELLES[code_pari].format(dom=dom, ext=ext),
            "confiance": confiance,
            "analysis": analyse,
            "coupon_code": coupon,
            "stats": stats,
            "promo_code": MON_CODE_PROMO,
            "lien_inscription": MON_LIEN_INSCRIPTION,
            "lien_telegram": MON_LIEN_TELEGRAM,
        }
        try:
            envoyer_supabase(ligne)
            print("Envoyé à Supabase.")
        except Exception as e:
            print("[Supabase] échec :", e)
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())

