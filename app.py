import os, math, datetime as dt, requests, streamlit as st
from zoneinfo import ZoneInfo
st.set_page_config(page_title="MORYSON FOOT AI", page_icon="⚽", layout="wide")
st.title("⚽ MORYSON FOOT AI — Tableau de bord privé")
KEY = st.secrets.get("API_FOOTBALL_KEY", "")
PASSWORD = st.secrets.get("APP_PASSWORD", "")
if not PASSWORD:
    st.error("Définir APP_PASSWORD dans les secrets de l'hébergeur."); st.stop()
if not st.session_state.get("authenticated"):
    with st.form("login"):
        pwd=st.text_input("Mot de passe",type="password")
        if st.form_submit_button("Se connecter"):
            import hmac
            if hmac.compare_digest(pwd,PASSWORD): st.session_state.authenticated=True; st.rerun()
            else: st.error("Mot de passe incorrect")
    st.stop()
if st.sidebar.button("Déconnexion"):
    st.session_state.authenticated=False; st.rerun()
if not KEY:
    st.warning("Configurer API_FOOTBALL_KEY pour activer les données réelles."); st.stop()
BASE="https://v3.football.api-sports.io/"
@st.cache_data(ttl=3600,show_spinner=False)
def api(endpoint,params):
    r=requests.get(BASE+endpoint,params=params,headers={"x-apisports-key":KEY},timeout=25)
    r.raise_for_status()
    payload=r.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    return payload.get("response",[])
def pois(k,lam):
    return math.exp(-lam)*lam**k/math.factorial(k)
def forecast(h,a):
    vals=[(i,j,pois(i,h)*pois(j,a)) for i in range(16) for j in range(16)]
    vals.sort(key=lambda x:x[2],reverse=True)
    return vals[:3],(1-math.exp(-h))*(1-math.exp(-a)),1-sum(pois(k,h+a) for k in range(3))
def avg_goals(matches,team_id,side):
    vals=[]
    for m in matches:
        if m.get("fixture",{}).get("status",{}).get("short") not in ("FT","AET","PEN"): continue
        t=m.get("teams",{})
        if t.get(side,{}).get("id")!=team_id: continue
        g=m.get("goals",{})
        if g.get("home") is None or g.get("away") is None: continue
        vals.append((g["home"],g["away"]) if side=="home" else (g["away"],g["home"]))
    return vals
today=dt.datetime.now(ZoneInfo("Europe/Paris")).date()
day=st.date_input("Date des rencontres (heure France)",value=today)
limit=st.slider("Nombre maximal de matchs à analyser",5,100,20,5)
st.caption("Les données sont récupérées depuis API-Football. Le bouton recharge le cache. Le modèle utilise les derniers matchs terminés et sépare domicile/extérieur.")
if st.button("Actualiser les données"): st.cache_data.clear()
try:
    # Date API en UTC: inclure la veille et le lendemain pour couvrir les fuseaux horaires
    raw=[]
    for offset in (-1,0,1):
        raw+=api("fixtures",{"date":(day+dt.timedelta(days=offset)).isoformat()})
    fixtures=[]
    for f in raw:
        iso=f.get("fixture",{}).get("date")
        if not iso: continue
        local=dt.datetime.fromisoformat(iso.replace("Z","+00:00")).astimezone(ZoneInfo("Europe/Paris"))
        if local.date()==day and f.get("fixture",{}).get("status",{}).get("short")=="NS":
            fixtures.append((local,f))
    fixtures.sort(key=lambda t:t[0])
    st.info(f"{len(fixtures)} rencontres à venir trouvées pour cette date. Analyse limitée aux {limit} premières, triées par heure.")
    results=[]
    for local,f in fixtures[:limit]:
        home=f["teams"]["home"]; away=f["teams"]["away"]
        try:
            hmatches=api("fixtures",{"team":home["id"],"last":20})
            amatches=api("fixtures",{"team":away["id"],"last":20})
            h=avg_goals(hmatches,home["id"],"home")
            a=avg_goals(amatches,away["id"],"away")
            if len(h)<4 or len(a)<4:
                results.append({"Heure":local.strftime("%H:%M"),"Compétition":f["league"]["name"],"Match":home["name"]+" – "+away["name"],"Données":"Insuffisantes","Top scores":"—","BTTS":"—","Over 2.5":"—"})
                continue
            hf=sum(x[0] for x in h)/len(h); ha=sum(x[1] for x in h)/len(h)
            af=sum(x[0] for x in a)/len(a); aa=sum(x[1] for x in a)/len(a)
            # Regularized heuristic: avoids extreme forecasts, not calibrated to market.
            lam_h=max(.25,min(3.5,.5*hf+.5*aa))
            lam_a=max(.25,min(3.5,.5*af+.5*ha))
            top,btts,over=forecast(lam_h,lam_a)
            scores=", ".join(f"{x}-{y} ({p:.1%})" for x,y,p in top)
            results.append({"Heure":local.strftime("%H:%M"),"Compétition":f["league"]["name"],"Match":home["name"]+" – "+away["name"],"Données":f"{len(h)} dom. / {len(a)} ext.","Top scores":scores,"BTTS":f"{btts:.1%}","Over 2.5":f"{over:.1%}"})
        except Exception as ex:
            results.append({"Heure":local.strftime("%H:%M"),"Compétition":f["league"]["name"],"Match":home["name"]+" – "+away["name"],"Données":"Erreur API","Top scores":"—","BTTS":"—","Over 2.5":"—"})
    st.dataframe(results,use_container_width=True,hide_index=True)
    if results:
        import csv,io
        out=io.StringIO(); w=csv.DictWriter(out,fieldnames=results[0].keys());w.writeheader();w.writerows(results)
        st.download_button("Exporter le rapport CSV",out.getvalue().encode("utf-8-sig"),file_name=f"moryson_{day}.csv",mime="text/csv")
except Exception as ex:
    st.error("Impossible de charger les matchs. Vérifier la clé API, le quota et la connexion.")
    st.code(str(ex))
st.divider()
st.caption("Prototype expérimental : modèle Poisson simplifié non calibré, sans blessures, compositions ni xG. Aucun score garanti. Les ligues peu documentées peuvent ne pas être analysables.")
