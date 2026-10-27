execute_script(JS_CLIC_PARI, marche, issue)
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
---------------------------- SUPABASE ----------------------------
def envoyer_supabase(ligne): url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/pronostics?on_conflict=fixture_id" entetes = { "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "resolution=merge-duplicates,return=minimal", } http_json(url, "POST", entetes, [ligne])
------------------------------ MAIN ------------------------------
def main(): date_jour = datetime.now(FUSEAU).strftime("%Y-%m-%d") print("=== CC13 Prédiction -", date_jour, "===") matchs = choisir_matchs(date_jour) if not matchs: print("Aucun match exploitable aujourd'hui.") return 0
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
if name == "main": sys.exit(main())
