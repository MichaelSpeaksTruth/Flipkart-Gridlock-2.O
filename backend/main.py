import sys
import os
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

# Add the local theme2 directory to sys.path so we can import recommend.py
THEME2_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "theme2"))
sys.path.insert(0, THEME2_DIR)

import recommend as rec

app = FastAPI(title="Corridor Watch API")

# Setup CORS for Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update this with the specific Vercel URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load metadata needed for the frontend
ARTIFACT_DIR = os.path.join(THEME2_DIR, "artifacts")
with open(os.path.join(ARTIFACT_DIR, "meta.json")) as f:
    META = json.load(f)

CORRIDOR_ZONE = (pd.read_csv(os.path.join(ARTIFACT_DIR, "corridor_zone_map.csv"))
                    .set_index("corridor")["zone"])
CORRIDOR_CENT = (pd.read_csv(os.path.join(ARTIFACT_DIR, "corridor_centroids.csv"))
                    .set_index("corridor")[["mean_lat", "mean_lon"]])
CORRIDOR_POLICE = (pd.read_csv(os.path.join(ARTIFACT_DIR, "corridor_police_map.csv"))
                     .set_index("corridor")["top_police_station"])

# Helper mapping for display labels to internal causes
CAUSE_LABEL = {
    "accident":             "Accident",
    "vehicle_breakdown":    "Vehicle Breakdown",
    "tree_fall":            "Tree Fall",
    "congestion":           "Congestion",
    "procession":           "Procession",
    "protest":              "Protest",
    "vip_movement":         "VIP Movement",
    "public_event":         "Public Event",
    "Fog / Low Visibility": "Fog / Low Visibility",
    "pot_holes":            "Pot Holes",
    "road_conditions":      "Road Conditions",
    "water_logging":        "Water Logging",
    "construction":         "Construction",
    "Debris":               "Debris / Road Blockage",
    "others":               "Others",
    "test_demo":            "Test / Demo",
}
LABEL_TO_CAUSE = {v: k for k, v in CAUSE_LABEL.items()}

class AssessRequest(BaseModel):
    event_case: str
    corridor: str
    override_mode: str
    police_station: str = ""
    date: str
    time: str
    event_type: str
    authenticated: bool

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/meta")
def get_meta():
    named_corridors = sorted([c for c in META["cat_maps"]["corridor"] if c != "Non-corridor"])
    corridors = named_corridors + ["Non-corridor"]

    # Only return causes that have a label defined in our UI mapping
    causes = [CAUSE_LABEL.get(c, c) for c in META["cat_maps"]["event_cause"]]
    causes = sorted(list(set(causes)))

    police_stations = sorted(META["cat_maps"]["police_station"])

    # Build corridor GPS centroid map for frontend display
    centroid_map: dict = {}
    for corr, row in CORRIDOR_CENT.iterrows():
        centroid_map[str(corr)] = {
            "lat": round(float(row["mean_lat"]), 4),
            "lon": round(float(row["mean_lon"]), 4),
        }

    # Build corridor -> auto police station map for frontend display
    police_map: dict = {str(corr): str(ps) for corr, ps in CORRIDOR_POLICE.items()}

    # Build corridor -> event count map from centroids CSV (reread with count column)
    cent_full = pd.read_csv(os.path.join(ARTIFACT_DIR, "corridor_centroids.csv")).set_index("corridor")
    count_map: dict = {str(c): int(r["count"]) for c, r in cent_full.iterrows()}

    return {
        "event_cases": causes,
        "corridors": corridors,
        "police_stations": police_stations,
        "corridor_centroids": centroid_map,
        "corridor_police": police_map,
        "corridor_event_counts": count_map,
    }

@app.post("/api/assess")
def assess_risk(req: AssessRequest):
    # Parse inputs
    event_cause = LABEL_TO_CAUSE.get(req.event_case, req.event_case)
    
    # Date and Time parsing
    # Expected formats: date "YYYY/MM/DD" (or "YYYY-MM-DD"), time "HH:MM"
    dt_str = f"{req.date.replace('/', '-')} {req.time}"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except ValueError:
        dt = datetime.now() # Fallback
        
    hour = dt.hour
    dow = dt.weekday()
    is_weekend = dow >= 5
    is_peak = 10 <= hour <= 17

    # Logic from app.py for zones and police stations
    zones = [z for z in META["cat_maps"]["zone"] if z != "Unknown"]
    default_zone = CORRIDOR_ZONE.get(req.corridor, zones[0]) if req.corridor in CORRIDOR_ZONE else zones[0]
    zone = default_zone if default_zone in zones else zones[0]

    if req.override_mode.lower() == "manual" and req.police_station:
        police_station = req.police_station
    else:
        auto_ps = CORRIDOR_POLICE.get(req.corridor, META["cat_maps"]["police_station"][0])
        police_station = auto_ps if auto_ps in META["cat_maps"]["police_station"] else META["cat_maps"]["police_station"][0]

    event_type = req.event_type.lower()
    
    if req.corridor in CORRIDOR_CENT.index:
        lat = float(CORRIDOR_CENT.loc[req.corridor, "mean_lat"])
        lon = float(CORRIDOR_CENT.loc[req.corridor, "mean_lon"])
    else:
        lat, lon = 12.9716, 77.5946

    # Call recommendation logic
    result = rec.recommend(
        event_cause=event_cause,
        corridor=req.corridor,
        zone=zone,
        police_station=police_station,
        hour=hour,
        dow=dow,
        is_weekend=is_weekend,
        is_peak=is_peak,
        authenticated=req.authenticated,
        event_type=event_type,
        lat=lat,
        lon=lon
    )
    
    # Generate Operational Summary
    # Extract recommendation line specifically
    lines = result["message"].split("\n")
    rec_line = "Monitor closely."
    for line in lines:
        if line.startswith("Recommendation:"):
            rec_line = line.replace("Recommendation:", "").strip()
            break
            
    summary = (f"A {req.event_case.lower()} reported on {req.corridor} presents a {result['risk_label'].lower()} "
               f"likelihood of requiring a temporary road closure. Historical data indicates an estimated clearance time of "
               f"approximately {result['eta_min']:.0f} minutes. Current corridor fragility is "
               f"{'moderate' if 2.5 <= result['fragility_score'] < 4.0 else ('high' if result['fragility_score'] >= 4.0 else 'low')}. "
               f"{rec_line.capitalize()}")

    return {
        "risk_probability": round(result['closure_prob'] * 100, 1),
        "risk_label": result["risk_label"],
        "eta_minutes": round(result['eta_min'], 0),
        "fragility_score": round(result['fragility_score'], 1),
        "diversion": ", ".join(result['diversion']) if result['diversion'] else "None available",
        "recommendation": rec_line,
        "summary": summary
    }
