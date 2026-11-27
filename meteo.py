from datetime import datetime, timedelta
import json
import os
import pandas as pd
import requests

# --- CONFIGURAZIONE ZONA ---
NOME_ZONA = "Scandiano & Zona"
LAT = 44.598
LON = 10.695
STORICO_FILE = "storico_meteo.csv"

# 1. SCARICA PREVISIONI (Oggi + 4 giorni = 5 giorni totali)
url_forecast = "https://api.open-meteo.com/v1/forecast"
params_forecast = {
    "latitude": LAT,
    "longitude": LON,
    "daily": [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    ],
    "hourly": ["temperature_2m", "precipitation"],
    "models": ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"],
    "timezone": "Europe/Rome",
    "forecast_days": 5,
}
res_f = requests.get(url_forecast, params=params_forecast).json()
daily = res_f["daily"]
hourly = res_f["hourly"]

# 2. SCARICA DATI REALI DI IERI (per la pagella di precisione)
ieri = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
oggi = datetime.now().strftime("%Y-%m-%d")

url_past = "https://api.open-meteo.com/v1/forecast"
params_past = {
    "latitude": LAT,
    "longitude": LON,
    "daily": [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    ],
    "past_days": 2,
    "forecast_days": 1,
    "models": "best_match",
    "timezone": "Europe/Rome",
}
res_p = requests.get(url_past, params=params_past).json()
idx_ieri = res_p["daily"]["time"].index(ieri)
reale_tmax = res_p["daily"]["temperature_2m_max"][idx_ieri]
reale_tmin = res_p["daily"]["temperature_2m_min"][idx_ieri]
reale_pioggia = res_p["daily"]["precipitation_sum"][idx_ieri]

# 3. GESTIONE ARCHIVIO STORICO E CALCOLO PRECISIONE
nuova_riga = {
    "data_previsione": oggi,
    "target_data": daily["time"][1],  # Previsione fatta oggi per domani
    "ecmwf_tmax": daily["temperature_2m_max_ecmwf_ifs025"][1],
    "gfs_tmax": daily["temperature_2m_max_gfs_seamless"][1],
    "icon_tmax": daily["temperature_2m_max_icon_seamless"][1],
    "ecmwf_pioggia": daily["precipitation_sum_ecmwf_ifs025"][1],
    "gfs_pioggia": daily["precipitation_sum_gfs_seamless"][1],
    "icon_pioggia": daily["precipitation_sum_icon_seamless"][1],
    "reale_tmax": None,
}

if os.path.exists(STORICO_FILE):
  df_storico = pd.read_csv(STORICO_FILE)
else:
  df_storico = pd.DataFrame(columns=nuova_riga.keys())

# Aggiorna il dato reale di ieri se avevamo salvato una previsione per ieri
if ieri in df_storico["target_data"].values:
  df_storico.loc[df_storico["target_data"] == ieri, "reale_tmax"] = reale_tmax

# Aggiungi la previsione di oggi (evitando duplicati se eseguito più volte nello stesso giorno)
df_storico = df_storico[df_storico["data_previsione"] != oggi]
df_storico = pd.concat(
    [df_storico, pd.DataFrame([nuova_riga])], ignore_index=True
)
df_storico.to_csv(STORICO_FILE, index=False)

# Calcola classifica precisione sugli ultimi giorni verificati
verificati = df_storico.dropna(subset=["reale_tmax"])
if len(verificati) > 0:
  err_ecmwf = (verificati["ecmwf_tmax"] - verificati["reale_tmax"]).abs().mean()
  err_gfs = (verificati["gfs_tmax"] - verificati["reale_tmax"]).abs().mean()
  err_icon = (verificati["icon_tmax"] - verificati["reale_tmax"]).abs().mean()
  # Converte l'errore medio in un punteggio percentuale intuitivo
  score_ecmwf = max(0, round(100 - (err_ecmwf * 10)))
  score_gfs = max(0, round(100 - (err_gfs * 10)))
  score_icon = max(0, round(100 - (err_icon * 10)))
  testo_classifica = f"ECMWF: {score_ecmwf}% (err. {err_ecmwf:.1f}°C) | ICON: {score_icon}% (err. {err_icon:.1f}°C) | GFS: {score_gfs}% (err. {err_gfs:.1f}°C)"
else:
  testo_classifica = (
      "Raccolta dati avviata oggi. La classifica apparirà da domani!"
  )

# 4. CALCOLO AFFIDABILITÀ ODIERNA
tmax_oggi = [
    daily["temperature_2m_max_ecmwf_ifs025"][0],
    daily["temperature_2m_max_gfs_seamless"][0],
    daily["temperature_2m_max_icon_seamless"][0],
]
tmin_oggi = [
    daily["temperature_2m_min_ecmwf_ifs025"][0],
    daily["temperature_2m_min_gfs_seamless"][0],
    daily["temperature_2m_min_icon_seamless"][0],
]
spread = max(tmax_oggi) - min(tmax_oggi)

if spread <= 1.2:
  aff_testo = "ALTA (Modelli concordi)"
  aff_colore = "#22c55e"
elif spread <= 2.5:
  aff_testo = "MEDIA (Leggere differenze)"
  aff_colore = "#eab308"
else:
  aff_testo = "BASSA (Modelli in disaccordo)"
  aff_colore = "#ef4444"

# Prepara dati per il grafico delle prossime 48 ore
ore_48 = [t.split("T")[1] for t in hourly["time"][:48]]
ecmwf_48 = hourly["temperature_2m_ecmwf_ifs025"][:48]
gfs_48 = hourly["temperature_2m_gfs_seamless"][:48]
icon_48 = hourly["temperature_2m_icon_seamless"][:48]

# 5. GENERAZIONE PAGINA WEB (index.html)
html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meteo {NOME_ZONA}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f1f5f9; color: #1e293b; margin: 0; padding: 16px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; font-size: 1.5rem; color: #0f172a; }}
        .header p {{ margin: 4px 0 0; font-size: 0.85rem; color: #64748b; }}
        .card {{ background: white; border-radius: 16px; padding: 20px; margin-bottom: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
        .card h2 {{ margin-top: 0; font-size: 1.1rem; color: #334155; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }}
        .oggi-grid {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }}
        .temp-big {{ font-size: 2rem; font-weight: bold; color: #0f172a; }}
        .badge {{ padding: 8px 14px; border-radius: 999px; color: white; font-weight: bold; font-size: 0.9rem; background: {aff_colore}; }}
        .table-days {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9rem; }}
        .table-days th, .table-days td {{ padding: 8px; text-align: center; border-bottom: 1px solid #f1f5f9; }}
        .pagella {{ background: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 8px; font-size: 0.95rem; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>METEO {NOME_ZONA.upper()}</h1>
        <p>Aggiornato il {datetime.now().strftime("%d/%m/%Y alle %H:%M")}</p>
    </div>

    <div class="card">
        <h2>PREVISIONE DI OGGI E PROSSIMI 4 GIORNI</h2>
        <div class="oggi-grid">
            <div class="temp-big">Min {round(sum(tmin_oggi)/3, 1)}°C / Max {round(sum(tmax_oggi)/3, 1)}°C</div>
            <div class="badge">Affidabilità: {aff_testo}</div>
        </div>
        <table class="table-days">
            <tr><th>Giorno</th><th>ECMWF (Max)</th><th>GFS (Max)</th><th>ICON (Max)</th><th>Pioggia Media</th></tr>
            {"".join([f"<tr><td>{daily['time'][i][5:]}</td><td>{daily['temperature_2m_max_ecmwf_ifs025'][i]}°</td><td>{daily['temperature_2m_max_gfs_seamless'][i]}°</td><td>{daily['temperature_2m_max_icon_seamless'][i]}°</td><td>{round((daily['precipitation_sum_ecmwf_ifs025'][i]+daily['precipitation_sum_gfs_seamless'][i]+daily['precipitation_sum_icon_seamless'][i])/3, 1)} mm</td></tr>" for i in range(5)])}
        </table>
    </div>

    <div class="card">
        <h2>CONFRONTO TEMPERATURE (Prossime 48 ore)</h2>
        <canvas id="meteoChart" height="140"></canvas>
    </div>

    <div class="card">
        <h2>PAGELLA DI IERI & PRECISIONE STORICA</h2>
        <div class="pagella">
            <p style="margin:0 0 8px;"><strong>Consuntivo reale di ieri ({ieri[5:]}):</strong> Min {reale_tmin}°C / Max {reale_tmax}°C | Pioggia: {reale_pioggia} mm</p>
            <p style="margin:0; color:#1d4ed8; font-weight:bold;">{testo_classifica}</p>
        </div>
    </div>
</div>

<script>
    const ctx = document.getElementById('meteoChart').getContext('2d');
    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: {json.dumps(ore_48)},
            datasets: [
                {{ label: 'ECMWF', data: {json.dumps(ecmwf_48)}, borderColor: '#2563eb', tension: 0.3, pointRadius: 1 }},
                {{ label: 'GFS', data: {json.dumps(gfs_48)}, borderColor: '#dc2626', tension: 0.3, pointRadius: 1 }},
                {{ label: 'ICON', data: {json.dumps(icon_48)}, borderColor: '#16a34a', tension: 0.3, pointRadius: 1 }}
            ]
        }},
        options: {{ responsive: true, interaction: {{ mode: 'index', intersect: false }} }}
    }});
</script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)
print("Dashboard aggiornata con successo!")
