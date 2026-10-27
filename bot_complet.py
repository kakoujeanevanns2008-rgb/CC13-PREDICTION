#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CC13 Prédiction - bot quotidien (API-Football -> Groq -> 1xBet -> Supabase)"""

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
RAPIDAPI_KEY = secret("RAPIDAPI_KEY", "COLLE_ICI_TA_CLE_APIFOOTBALL")
GROQ_KEY = secret("GROQ_KEY", "COLLE_ICI_TA_CLE_GROQ")
SUPABASE_URL = secret("SUPABASE_URL", "https://VOTRE-PROJET.supabase.co")
SUPABASE_KEY = secret("SUPABASE_KEY", "COLLE_ICI_LA_CLE_SERVICE_ROLE")
MON_CODE_PROMO = secret("MON_CODE_PROMO", "MON_CODE_PROMO")
MON_LIEN_INSCRIPTION = secret("MON_LIEN_INSCRIPTION", "https://1xbet.ci")
MON_LIEN_TELEGRAM = secret("MON_LIEN_TELEGRAM", "https://t.me/VOTRE_CHAINE")
# ===============================================================

API_HOST = "v3.football.api-sports.io"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
BASE_1XBET = "https://1xbet.ci"
FUSEAU = ZoneInfo("Africa/Abidjan")
MAX_MATCHES = 3
PRIORITE = [2, 3, 848, 39, 140, 135, 78, 61, 94, 88, 12, 6]
DOSSIER_CAPTURES = "screenshots"

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
        print(f"[HTTP {e.code}] {url[:80]} -> {e.read().decode('utf-8', 'ignore')[:300]}")
        raise


# ------------------------- API-FOOTBALL -------------------------
def api_football(chemin, params):
    url = f"https://{API_HOST}/{chemin}?" + urllib.parse.urlencode(params)
    data = http_json(url, entetes={"x-apisports-key": RAPIDAPI_KEY})
    if data.get("errors"):
        print("[API-Football] erreurs :", data["errors"])
    return data.get("response", [])


def choisir_matchs(date_jour):
    fixtures = api_football("fixtures", {"date": date_jour, "timezone": "Africa/Abidjan"})
    print(f"{len(fixtures)} matchs trouvés pour {date_jour}")
    a_venir = [f for f in fixtures if f["fixture"]["status"]["short"] == "NS"]

    def cle(f):
        lid = f["league"]["id"]
        return PRIORITE.index(lid) if lid in PRIORITE else 999

    a_venir.sort(key=lambda f: (cle(f), f["fixture"]["date"]))
    return a_venir[:MAX_MATCHES]


_cache_classements = {}


def classement_ligue(ligue_id, saison):
    cle = (ligue_id, saison)
    if cle in _cache_classements:
        return _cache_classements[cle]
    resultat = {}
    try:
        rep = api_football("standings", {"league": ligue_id, "season": saison})
        for ligne in rep[0]["league"]["standings"][0]:
            a = ligne["all"]
            resultat[ligne["team"]["id"]] = (
                f'{ligne["rank"]}e - {ligne["points"]} pts - {a["played"]} J '
                f'({a["win"]}V {a["draw"]}N {a["lose"]}D)'
            )
    except Exception as e:
        print("[classement] indisponible :", e)
    _cache_classements[cle] = resultat
    return resultat


def convertir_forme(f):
    if not f:
        return "N/D"
    table = {"W": "V", "D": "N", "L": "D"}
    return " ".join(table.get(c, c) for c in f[-5:])


def construire_stats(fixture):
    fid = fixture["fixture"]["id"]
    dom = fixture["teams"]["home"]
    ext = fixture["teams"]["away"]
    stats = {
        "forme_domicile": "N/D",
        "forme_exterieur": "N/D",
        "h2h": [],
        "classement_domicile": "N/D",
        "classement_exterieur": "N/D",
        "probas": {},
        "conseil_api": "",
    }
    try:
        rep = api_football("predictions", {"fixture": fid})
        p = rep[0] if rep else None
    except Exception as e:
        print("[predictions] indisponible :", e)
        p = None

    if p:
        try:
            stats["forme_domicile"] = convertir_forme(p["teams"]["home"]["league"]["form"])
            stats["forme_exterieur"] = convertir_forme(p["teams"]["away"]["league"]["form"])
        except Exception:
            pass
        try:
            pc = p["predictions"]["percent"]
            stats["probas"] = {"domicile": pc["home"], "nul": pc["draw"], "exterieur": pc["away"]}
            stats["conseil_api"] = p["predictions"].get("advice") or ""
        except Exception:
            pass
        try:
            historique = sorted(p.get("h2h", []), key=lambda m: m["fixture"]["date"], reverse=True)[:5]
            for m in historique:
                stats["h2h"].append({
                    "date": m["fixture"]["date"][:10],
                    "match": f'{m["teams"]["home"]["name"]} - {m["teams"]["away"]["name"]}',
                    "score": f'{m["goals"]["home"]}-{m["goals"]["away"]}',
                })
        except Exception:
            pass

    classement = classement_ligue(fixture["league"]["id"], fixture["league"]["season"])
    stats["classement_domicile"] = classement.get(dom["id"], "N/D")
    stats["classement_exterieur"] = classement.get(ext["id"], "N/D")
    return stats


# ------------------------------ GROQ ------------------------------
def analyser_avec_groq(fixture, stats):
    dom = fixture["teams"]["home"]["name"]
    ext = fixture["teams"]["away"]["name"]
    choix = ", ".join(MARCHES.keys())
    consigne = (
        "Tu es un analyste de pronostics football. Réponds UNIQUEMENT avec un objet JSON "
        'de la forme {"analyse": "...", "pronostic": "...", "confiance": 65}. '
        "Règles : 'analyse' = exactement 3 phrases en français, basées sur les statistiques fournies, "
        f"sans inventer de données. 'pronostic' = une seule valeur parmi : {choix}. "
        "'confiance' = entier entre 50 et 85 (prudence : ne dépasse jamais 85)."
    )
    contenu = {
        "match": f"{dom} (domicile) vs {ext} (extérieur)",
        "competition": fixture["league"]["name"],
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
    print("Clé API-Football : longueur", len(RAPIDAPI_KEY))
    matchs = choisir_matchs(date_jour)
    if not matchs:
        print("Aucun match exploitable aujourd'hui.")
        return 0

    for i, f in enumerate(matchs, start=1):
        dom = f["teams"]["home"]["name"]
        ext = f["teams"]["away"]["name"]
        print(f"\n--- Match {i} : {dom} - {ext} ({f['league']['name']}) ---")
        try:
            stats = construire_stats(f)
            analyse, code_pari, confiance = analyser_avec_groq(f, stats)
        except Exception as e:
            print("[IA/stats] échec, match ignoré :", e)
            continue
        print(f"Pronostic : {code_pari} ({confiance}%)")

        coupon = recuperer_coupon(dom, ext, code_pari, f"match{i}")
        print("Code coupon :", coupon or "indisponible")

        ligne = {
            "fixture_id": f["fixture"]["id"],
            "date_match": date_jour,
            "league": f["league"]["name"],
            "home_team": dom,
            "away_team": ext,
            "match_name": f"{dom} - {ext}",
            "kickoff": f["fixture"]["date"],
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

