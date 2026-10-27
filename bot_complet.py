import os
import json
import urllib.request
from datetime import datetime

# =====================================================================
# 🔑 RÉCUPÉRATION DES CLÉS DE SÉCURITÉ DEPUIS GITHUB SETTINGS
# =====================================================================
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
GROQ_KEY = os.getenv("GROQ_KEY", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

print("🤖 --- DÉMARRAGE DU BOT DE PRONOSTICS ---")
print(f"Vérification des secrets - API Football : {len(RAPIDAPI_KEY)} chars, Groq : {len(GROQ_KEY)} chars")

# =====================================================================
# ⚽ ÉTAPE 1 : RÉCUPÉRATION DES MATCHS DU JOUR (MÉTHODE PAR DATE 100% GRATUITE)
# =====================================================================
date_aujourdhui = datetime.now().strftime("%Y-%m-%d")
print(f"📅 Recherche des matchs pour la date du jour : {date_aujourdhui}")

url_football = f"https://rapidapi.com{date_aujourdhui}"
headers_football = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "://rapidapi.com"
}

req_foot = urllib.request.Request(url_football, headers=headers_football)
matchs_selectionnes = []

try:
    with urllib.request.urlopen(req_foot) as response:
        data_foot = json.loads(response.read().decode("utf-8"))
        fixtures = data_foot.get("response", [])
        print(f"⚽ {len(fixtures)} matchs trouvés au total sur l'API.")
        
        # On ne prend que les 3 premiers matchs pour rester dans le forfait gratuit
        for f in fixtures[:3]:
            matchs_selectionnes.append({
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "league": f["league"]["name"]
            })
except Exception as e:
    print(f"❌ Erreur lors de la récupération des matchs : {e}")

# =====================================================================
# 🧠 ÉTAPE 2 & 3 : ANALYSE IA (LLAMA3) & SIMULATION DU COUPON
# =====================================================================
if not matchs_selectionnes:
    print("❌ Aucun match disponible pour l'analyse. Arrêt du bot.")
else:
    for m in matchs_selectionnes:
        nom_du_match = f"{m['home']} vs {m['away']}"
        print(f"\n🔮 Analyse de l'IA pour : {nom_du_match} ({m['league']})")
        
        # Envoi à l'IA Groq avec le modèle gratuit officiel Llama3-8b-8192
        url_groq = "https://groq.com"
        headers_groq = {
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }
        prompt = f"Donne un pronostic football rapide (V1, V2 ou Total) with a percentage of confidence and a quick explanation in French for the match : {nom_du_match}"
        
        data_groq = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            req_groq = urllib.request.Request(url_groq, data=json.dumps(data_groq).encode("utf-8"), headers=headers_groq)
            with urllib.request.urlopen(req_groq) as response_groq:
                res_groq = json.loads(response_groq.read().decode("utf-8"))
                analyse_ia = res_groq["choices"]["message"]["content"]
                print(f"✅ Analyse générée : {analyse_ia[:50]}...")
                
                # Simulation du robot 1xBet pour générer un code coupon de test visible
                import random
                import string
                code_simule = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                
                # =====================================================================
                # 📦 ÉTAPE 4 : ENVOI AUTOMATIQUE DANS SUPABASE
                # =====================================================================
                print("📤 Envoi des données vers la base de données Supabase...")
                url_supabase = f"{SUPABASE_URL}/rest/v1/pronostics"
                headers_supabase = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                }
                donnees_pari = {
                    "match_nom": nom_du_match,
                    "prediction": "V1 ou Total (Voir Analyse)",
                    "confiance": "85%",
                    "analyse_texte": analyse_ia,
                    "code_1xbet": code_simule
                }
                
                req_sub = urllib.request.Request(url_supabase, data=json.dumps(donnees_pari).encode("utf-8"), headers=headers_supabase)
                with urllib.request.urlopen(req_sub) as res_sub:
                    print(f"🎉 ÉLÉMENT ENREGISTRÉ AVEC SUCCÈS DANS SUPABASE POUR {nom_du_match} !")
                    
        except Exception as e:
            print(f"❌ Erreur lors du traitement de ce match : {e}")

print("\n🏁 --- FIN DU SCRIPT ---")

