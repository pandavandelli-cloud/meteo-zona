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

GIORNI_SETTIMANA = [
    "Lunedì",
    "Martedì",
    "Mercoledì",
    "Giovedì",
    "Venerdì",
    "Sabato",
    "Domenica",
]


def formatta_giorno(data_str, indice):
  dt = datetime.strptime(data_str, "%Y-%m-%d")
  nome = GIORNI_SETTIMANA[dt.weekday()]
  data_breve = dt.strftime("%d/%m")
  if indice == 0:
    return f"Oggi <span class='sub-date'>({data_breve})</span>"
  if indice == 1:
    return f"Domani <span class='sub-date'>({data_breve})</span>"
  return f"{nome} <span class='sub-date'>({data_breve})</span>"


def info_meteo(codice):
  if codice is None or pd.isna(codice):
    return "❓", "Non disp."
  c = int(codice)
  if c == 0:
    return "☀️", "Sereno"
  if c in [1, 2]:
    return "⛅", "Poco nuvoloso"
  if c == 3:
    return "☁️", "Nuvoloso"
  if c in [45, 48]:
    return "🌫️", "Nebbia"
  if c in [51, 53, 55, 56, 57]:
    return "🌦️", "Pioviggine"
  if c in [61, 63, 65, 66, 67, 80, 81, 82]:
    return "🌧️", "Pioggia"
  if c in [71, 73, 75, 77, 85, 86]:
    return "❄️", "Neve"
  if c in [95, 96, 99]:
    return "⛈️", "Temporale"
  return "🌤️", "Variabile"


# 1. SCARICA PREVISIONI (Oggi + 4 giorni = 5 giorni totali)
url_forecast = "https://api.open-meteo.com/v1/forecast"
params_forecast = {
    "latitude": LAT,
    "longitude": LON,
    "daily": [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    ],
    "hourly": ["temperature_2m", "precipitation"],
    "models": ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"],
    "timezone": "Europe/Rome",
    "forecast_days": 5,
}
res_f = requests.get(url_forecast, params=params_forecast, timeout=15).json()
daily = res_f["daily"]
hourly = res_f["hourly"]

# 2. SCARICA DATI REALI DI IERI
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
res_p = requests.get(url_past, params=params_past, timeout=15).json()
idx_ieri = res_p["daily"]["time"].index(ieri)
reale_tmax = res_p["daily"]["temperature_2m_max"][idx_ieri]
reale_tmin = res_p["daily"]["temperature_2m_min"][idx_ieri]
reale_pioggia = res_p["daily"]["precipitation_sum"][idx_ieri]

# 3. GESTIONE ARCHIVIO STORICO E PRECISIONE
nuova_riga = {
    "data_previsione": oggi,
    "target_data": daily["time"][1],
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

if ieri in df_storico["target_data"].values:
  df_storico.loc[df_storico["target_data"] == ieri, "reale_tmax"] = reale_tmax

df_storico = df_storico[df_storico["data_previsione"] != oggi]
df_storico = pd.concat(
    [df_storico, pd.DataFrame([nuova_riga])], ignore_index=True
)
df_storico.to_csv(STORICO_FILE, index=False)

verificati = df_storico.dropna(subset=["reale_tmax"])
if len(verificati) > 0:
  err_ecmwf = (verificati["ecmwf_tmax"] - verificati["reale_tmax"]).abs().mean()
  err_gfs = (verificati["gfs_tmax"] - verificati["reale_tmax"]).abs().mean()
  err_icon = (verificati["icon_tmax"] - verificati["reale_tmax"]).abs().mean()
  score_ecmwf = max(0, round(100 - (err_ecmwf * 10)))
  score_gfs = max(0, round(100 - (err_gfs * 10)))
  score_icon = max(0, round(100 - (err_icon * 10)))
  testo_classifica = f"""
    <div class='score-grid'>
        <div class='score-pill'><strong>ECMWF</strong><span>{score_ecmwf}%</span><small>err. {err_ecmwf:.1f}°C</small></div>
        <div class='score-pill'><strong>ICON</strong><span>{score_icon}%</span><small>err. {err_icon:.1f}°C</small></div>
        <div class='score-pill'><strong>GFS</strong><span>{score_gfs}%</span><small>err. {err_gfs:.1f}°C</small></div>
    </div>
    """
else:
  testo_classifica = "<p style='margin:0; color:#475569;'>Raccolta dati avviata oggi. La pagella comparirà da domani!</p>"

# 4. AFFIDABILITÀ ODIERNA
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
  aff_testo = "🟢 Alta affidabilità (Modelli concordi)"
  aff_bg = "rgba(34, 197, 94, 0.25)"
elif spread <= 2.5:
  aff_testo = "🟡 Media affidabilità (Leggere differenze)"
  aff_bg = "rgba(234, 179, 8, 0.3)"
else:
  aff_testo = "🔴 Bassa affidabilità (Modelli distanti)"
  aff_bg = "rgba(239, 68, 68, 0.3)"

ore_48 = [t.split("T")[1] for t in hourly["time"][:48]]
ecmwf_48 = hourly["temperature_2m_ecmwf_ifs025"][:48]
gfs_48 = hourly["temperature_2m_gfs_seamless"][:48]
icon_48 = hourly["temperature_2m_icon_seamless"][:48]

# Costruzione schede 5 giorni
cards_giorni = ""
for i in range(5):
  titolo_g = formatta_giorno(daily["time"][i], i)
  icona_g, desc_g = info_meteo(daily["weather_code_ecmwf_ifs025"][i])

  e_min, e_max = (
      daily["temperature_2m_min_ecmwf_ifs025"][i],
      daily["temperature_2m_max_ecmwf_ifs025"][i],
  )
  g_min, g_max = (
      daily["temperature_2m_min_gfs_seamless"][i],
      daily["temperature_2m_max_gfs_seamless"][i],
  )
  i_min, i_max = (
      daily["temperature_2m_min_icon_seamless"][i],
      daily["temperature_2m_max_icon_seamless"][i],
  )

  pioggia_m = round(
      (
          daily["precipitation_sum_ecmwf_ifs025"][i]
          + daily["precipitation_sum_gfs_seamless"][i]
          + daily["precipitation_sum_icon_seamless"][i]
      )
      / 3,
      1,
  )
  badge_pioggia = (
      f"<span class='rain-pill active'>💧 {pioggia_m} mm</span>"
      if pioggia_m > 0
      else "<span class='rain-pill'>Asciutto</span>"
  )

  cards_giorni += f"""
    <div class="day-row">
        <div class="day-left">
            <div class="day-icon">{icona_g}</div>
            <div>
                <div class="day-name">{titolo_g}</div>
                <div class="day-desc">{desc_g} • {badge_pioggia}</div>
            </div>
        </div>
        <div class="day-models">
            <div class="mod-box"><span class="mod-lbl">ECMWF</span><span class="t-min">{e_min}°</span> / <span class="t-max">{e_max}°</span></div>
            <div class="mod-box"><span class="mod-lbl">GFS</span><span class="t-min">{g_min}°</span> / <span class="t-max">{g_max}°</span></div>
            <div class="mod-box"><span class="mod-lbl">ICON</span><span class="t-min">{i_min}°</span> / <span class="t-max">{i_max}°</span></div>
        </div>
    </div>
    """

# 5. GENERAZIONE PAGINA WEB (index.html)
html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meteo {NOME_ZONA}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #eef2f6; color: #1e293b; margin: 0; padding: 12px; }}
        .container {{ max-width: 820px; margin: 0 auto; }}
        
        /* Intestazione Hero compatta */
        .hero {{ background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: white; border-radius: 16px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 6px 14px -4px rgba(30, 58, 138, 0.25); }}
        .hero-top {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 8px; }}
        .hero h1 {{ margin: 0; font-size: 1.1rem; letter-spacing: 0.3px; }}
        .hero-time {{ font-size: 0.75rem; opacity: 0.85; }}
        .live-badge {{ background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 99px; font-size: 0.7rem; font-weight: 600; }}
        
        .hero-main {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-top: 10px; }}
        .now-temp-box {{ display: flex; align-items: center; gap: 10px; }}
        .now-icon {{ font-size: 2.2rem; line-height: 1; }}
        .now-temp {{ font-size: 2rem; font-weight: 800; line-height: 1; }}
        .now-desc {{ font-size: 0.88rem; opacity: 0.95; margin-top: 2px; }}
        .hero-stats {{ background: rgba(255,255,255,0.12); padding: 8px 12px; border-radius: 10px; font-size: 0.8rem; line-height: 1.4; }}
        .aff-pill {{ display: inline-block; background: {aff_bg}; padding: 2px 8px; border-radius: 6px; font-weight: 600; margin-top: 3px; font-size: 0.75rem; }}

        /* Schede generali */
        .card {{ background: white; border-radius: 16px; padding: 16px; margin-bottom: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
        .card h2 {{ margin: 0 0 12px; font-size: 1rem; color: #334155; display: flex; align-items: center; justify-content: space-between; }}

        /* Scorrimento orario stile app */
        .hourly-scroll {{ display: flex; gap: 8px; overflow-x: auto; padding-bottom: 6px; scrollbar-width: thin; }}
        .hour-card {{ min-width: 72px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 8px 4px; text-align: center; flex-shrink: 0; }}
        .hour-time {{ font-size: 0.78rem; font-weight: 700; color: #475569; }}
        .hour-icon {{ font-size: 1.35rem; margin: 4px 0; }}
        .hour-temp {{ font-size: 1rem; font-weight: 800; color: #0f172a; }}
        .hour-rain {{ font-size: 0.7rem; color: #0284c7; font-weight: 600; margin-top: 3px; min-height: 13px; }}
        .hour-wind {{ font-size: 0.68rem; color: #64748b; margin-top: 2px; }}

        /* Lista 5 giorni friendly */
        .day-row {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }}
        .day-row:last-child {{ border-bottom: none; padding-bottom: 0; }}
        .day-left {{ display: flex; align-items: center; gap: 10px; min-width: 185px; }}
        .day-icon {{ font-size: 1.8rem; width: 34px; text-align: center; }}
        .day-name {{ font-weight: 700; font-size: 0.95rem; color: #0f172a; }}
        .sub-date {{ font-weight: 400; color: #64748b; font-size: 0.82rem; }}
        .day-desc {{ font-size: 0.8rem; color: #475569; margin-top: 2px; }}
        .rain-pill {{ background: #f1f5f9; color: #64748b; padding: 2px 6px; border-radius: 6px; font-size: 0.72rem; }}
        .rain-pill.active {{ background: #e0f2fe; color: #0369a1; font-weight: 600; }}

        .day-models {{ display: flex; gap: 6px; flex-wrap: wrap; }}
        .mod-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 8px; text-align: center; font-size: 0.82rem; min-width: 78px; }}
        .mod-lbl {{ display: block; font-size: 0.65rem; font-weight: 700; color: #64748b; letter-spacing: 0.4px; margin-bottom: 1px; }}
        .t-min {{ color: #0284c7; font-weight: 700; }}
        .t-max {{ color: #ea580c; font-weight: 700; }}

        /* Pagella precisione */
        .ieri-box {{ background: #f8fafc; padding: 10px 12px; border-radius: 10px; font-size: 0.88rem; margin-bottom: 10px; border-left: 4px solid #3b82f6; }}
        .score-grid {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .score-pill {{ flex: 1; min-width: 85px; background: #eff6ff; border-radius: 10px; padding: 8px; text-align: center; }}
        .score-pill strong {{ display: block; font-size: 0.72rem; color: #1e40af; }}
        .score-pill span {{ display: block; font-size: 1.2rem; font-weight: 800; color: #1d4ed8; margin: 2px 0; }}
        .score-pill small {{ font-size: 0.72rem; color: #475569; }}
    </style>
</head>
<body>
<div class="container">

    <div class="hero">
        <div class="hero-top">
            <div>
                <h1>📍 {NOME_ZONA} <span class="hero-time">• Modelli {datetime.now().strftime("%d/%m %H:%M")} • <span id="ora-live">aggiornamento...</span></span></h1>
            </div>
            <div class="live-badge">● LIVE</div>
        </div>
        <div class="hero-main">
            <div class="now-temp-box">
                <div class="now-icon" id="icon-live">🌤️</div>
                <div>
                    <div class="now-temp" id="temp-live">--°</div>
                    <div class="now-desc" id="tempo-live">Caricamento...</div>
                </div>
            </div>
            <div class="hero-stats">
                <div>Oggi: <strong>Min {round(sum(tmin_oggi)/3, 1)}°</strong> / <strong>Max {round(sum(tmax_oggi)/3, 1)}°</strong> • Umidità: <strong><span id="umidita-live">--</span>%</strong></div>
                <div class="aff-pill">{aff_testo}</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>⏱️ PROSSIME 24 ORE <span style="font-size:0.75rem; font-weight:normal; color:#64748b;">(scorri →)</span></h2>
        <div class="hourly-scroll" id="fascia-oraria">
            <div style="padding:10px; color:#64748b; font-size:0.9rem;">Caricamento ore...</div>
        </div>
    </div>

    <div class="card">
        <h2>📅 PREVISIONE 5 GIORNI <span style="font-size:0.75rem; font-weight:normal; color:#64748b;">(Min / Max per modello)</span></h2>
        {cards_giorni}
    </div>

    <div class="card">
        <h2>📈 CONFRONTO TEMPERATURE (48 ORE)</h2>
        <canvas id="meteoChart" height="140"></canvas>
    </div>

    <div class="card">
        <h2>🏆 CHI CI HA PRESO DI PIÙ? (Storico Zona)</h2>
        <div class="ieri-box">
            <strong>Consuntivo reale di ieri ({ieri[8:10]}/{ieri[5:7]}):</strong> Min <span class="t-min">{reale_tmin}°C</span> / Max <span class="t-max">{reale_tmax}°C</span> • Pioggia: <strong>{reale_pioggia} mm</strong>
        </div>
        {testo_classifica}
    </div>

</div>

<script>
    function getMeteoInfo(c) {{
        if (c === 0) return {{ icon: "☀️", text: "Sereno" }};
        if (c === 1 || c === 2) return {{ icon: "⛅", text: "Poco nuvoloso" }};
        if (c === 3) return {{ icon: "☁️", text: "Nuvoloso" }};
        if (c === 45 || c === 48) return {{ icon: "🌫️", text: "Nebbia" }};
        if ([51,53,55,56,57].includes(c)) return {{ icon: "🌦️", text: "Pioviggine" }};
        if ([61,63,65,66,67,80,81,82].includes(c)) return {{ icon: "🌧️", text: "Pioggia" }};
        if ([71,73,75,77,85,86].includes(c)) return {{ icon: "❄️", text: "Neve" }};
        if ([95,96,99].includes(c)) return {{ icon: "⛈️", text: "Temporale" }};
        return {{ icon: "🌤️", text: "Variabile" }};
    }}

    fetch("https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,weather_code&hourly=temperature_2m,precipitation,weather_code,wind_speed_10m&forecast_days=2&timezone=Europe%2FRome")
        .then(r => r.json())
        .then(data => {{
            const cur = data.current;
            const infoCur = getMeteoInfo(cur.weather_code);
            document.getElementById("temp-live").textContent = Math.round(cur.temperature_2m * 10) / 10 + "°";
            document.getElementById("icon-live").textContent = infoCur.icon;
            document.getElementById("tempo-live").textContent = infoCur.text;
            document.getElementById("umidita-live").textContent = cur.relative_humidity_2m;
            document.getElementById("ora-live").textContent = "rilevato alle " + cur.time.split("T")[1];

            const h = data.hourly;
            const oraAttualeStr = cur.time.slice(0, 13);
            let idxStart = h.time.findIndex(t => t.startsWith(oraAttualeStr));
            if (idxStart === -1) idxStart = 0;

            let cardsHtml = "";
            for (let i = idxStart; i < Math.min(idxStart + 24, h.time.length); i++) {{
                const ora = h.time[i].slice(11, 16);
                const giorno = (i > idxStart && ora === "00:00") ? h.time[i].slice(8, 10) + "/" + h.time[i].slice(5, 7) : ora;
                const infoH = getMeteoInfo(h.weather_code[i]);
                const temp = Math.round(h.temperature_2m[i]) + "°";
                const pioggia = h.precipitation[i] > 0 ? "💧 " + h.precipitation[i] + "mm" : "";
                const vento = Math.round(h.wind_speed_10m[i]) + " km/h";

                cardsHtml += `
                <div class="hour-card">
                    <div class="hour-time">${{giorno}}</div>
                    <div class="hour-icon">${{infoH.icon}}</div>
                    <div class="hour-temp">${{temp}}</div>
                    <div class="hour-rain">${{pioggia}}</div>
                    <div class="hour-wind">💨 ${{vento}}</div>
                </div>`;
            }}
            document.getElementById("fascia-oraria").innerHTML = cardsHtml;
        }})
        .catch(() => {{
            document.getElementById("ora-live").textContent = "dato live non raggiungibile";
        }});

    const ctx = document.getElementById('meteoChart').getContext('2d');
    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: {json.dumps(ore_48)},
            datasets: [
                {{ label: 'ECMWF', data: {json.dumps(ecmwf_48)}, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.08)', fill: true, tension: 0.35, pointRadius: 1 }},
                {{ label: 'GFS', data: {json.dumps(gfs_48)}, borderColor: '#ea580c', tension: 0.35, pointRadius: 1 }},
                {{ label: 'ICON', data: {json.dumps(icon_48)}, borderColor: '#16a34a', tension: 0.35, pointRadius: 1 }}
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
print("Dashboard friendly compatta aggiornata con successo!")
