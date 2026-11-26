# Reihe „Finde die falsch platzierte Flagge!“ – ab 26.11.2026

Format: Europakarte (Ausschnitt) mit 3 Flaggen-Pins A/B/C, eine Flagge sitzt im falschen Land. Frage + Antworten ab Sekunde 0,
5-s-Countdown (5-4-3-2-1 + Ticken), Auflösung: falsche Flagge rotes X + Gastland rot, richtige Pins grün umkreist, Antwort grün + Hand hakt ab,
Punktestand 1/3–3/3, falsche Flagge fliegt bei „Sie gehört nach …“ ins Heimatland (grün). Runde 3 = „DIE SCHWERSTE!“. Outro mit Abo-Button + Bing, Wisch-Loop zu Runde 1.

Karte offline: `npm i world-atlas@2.0.2 topojson-client@3.1.0` + `node geo.mjs` → countries.geojson (Natural Earth 50m, Ländernamen englisch).
Render: `python3 falsch_flagge_quiz.py falsch_flaggen_teil<N>.json Falsche-Flagge-Teil<N>.mp4 --stimme el_falsch<N> --tempo 1.25 --tempo-aufl 1.3 --flug 0.68` (~4 min), Prüfbilder mit `--still`.
JSON je Runde: bbox [lon0, lat0, lon1, lat1], pins (flagge, land = Name in geojson, lonlat), antworten, richtig (0-basiert), heimat (land, lonlat). Flaggen in flag() ergänzen.
Pins mind. ~200 px auseinander (Norwegen/Schweden sonst überlappend).
Stimme Elli (eleven_v4, je 1 Take, ~1.900 Credits gesamt): q0 mit Hook „Nur drei Prozent finden alle drei falschen Flaggen!“, q1, q2, r0–r2 „Richtig, B! … Sie gehört nach …“, outro „… Teil <N+1> kommt morgen … Schaffst du alle drei?“.
Länge Teil 1: 61,5 s (lange Sprechtexte + 3 × 5 s Countdown).

## Teile
- Teil 1 (26.11.2026): R1 Westeuropa: Spanien / Italien (B, sitzt in Frankreich) / Deutschland. R2 Nordeuropa: Schweden / Norwegen / Finnland (C, sitzt in Dänemark).
  R3: Portugal / Griechenland / Österreich (C, sitzt in Ungarn). Titel: „🗺️ Finde die falsche Flagge! Nur 3 % schaffen 3/3“.

## Ideen für Teil 2+
Rumänien↔Tschad, Irland↔Elfenbeinküste, Monaco↔Indonesien/Polen, Niederlande↔Luxemburg, Slowakei↔Slowenien, Litauen↔Bolivien, Belgien↔Deutschland.
