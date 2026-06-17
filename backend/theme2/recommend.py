"""
Theme 2: Event-Driven Congestion - recommendation engine
Combines closure-risk model output + ETA lookup + corridor fragility index
into a single operator-facing recommendation. Pure rule logic on top of
the artifacts produced by train.py -- no model is trained here.
"""
import json, os
import joblib
import numpy as np
import pandas as pd

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), 'artifacts')

with open(os.path.join(ARTIFACT_DIR, 'meta.json')) as f:
    META = json.load(f)
CLOSURE_MODELS = joblib.load(os.path.join(ARTIFACT_DIR, 'closure_models.pkl'))
ETA_LOOKUP = pd.read_csv(os.path.join(ARTIFACT_DIR, 'eta_lookup.csv')).set_index('event_cause')['eta_min']
FRAGILITY = pd.read_csv(os.path.join(ARTIFACT_DIR, 'corridor_fragility.csv')).set_index('corridor')
CORRIDOR_ZONE = pd.read_csv(os.path.join(ARTIFACT_DIR, 'corridor_zone_map.csv')).set_index('corridor')['zone']

GLOBAL_ETA_FALLBACK = ETA_LOOKUP.mean()


def _encode(cat_col, value):
    cats = META['cat_maps'][cat_col]
    return cats.index(value) if value in cats else -1


def predict_closure_risk(event_cause, corridor, zone, police_station,
                          hour, dow, is_weekend, is_peak, authenticated, event_type, lat, lon):
    row = pd.DataFrame([{
        'event_cause_code': _encode('event_cause', event_cause),
        'corridor_code': _encode('corridor', corridor),
        'zone_code': _encode('zone', zone),
        'police_station_code': _encode('police_station', police_station),
        'hour': hour, 'dow': dow, 'is_weekend': int(is_weekend), 'is_peak': int(is_peak),
        'authenticated_bin': int(authenticated), 'event_type_bin': int(event_type == 'planned'),
        'latitude': lat, 'longitude': lon,
    }])[META['features']]
    probs = [m.predict_proba(row)[:, 1][0] for m in CLOSURE_MODELS]
    return float(np.mean(probs))


def get_eta_min(event_cause):
    return float(ETA_LOOKUP.get(event_cause, GLOBAL_ETA_FALLBACK))


def get_fragility(corridor):
    if corridor in FRAGILITY.index:
        row = FRAGILITY.loc[corridor]
        return float(row['fragility_score']), bool(row['is_named_corridor'])
    return 0.0, False


def suggest_diversion(corridor, zone, top_n=1):
    """Suggest the lowest-fragility named corridor in the same zone, excluding the current one."""
    same_zone = CORRIDOR_ZONE[CORRIDOR_ZONE == zone].index
    candidates = FRAGILITY[(FRAGILITY['is_named_corridor']) & (FRAGILITY.index.isin(same_zone))
                            & (FRAGILITY.index != corridor)]
    if candidates.empty:
        return None
    return candidates.sort_values('fragility_score').head(top_n).index.tolist()


def recommend(event_cause, corridor, zone, police_station, hour, dow,
              is_weekend, is_peak, authenticated, event_type, lat, lon):
    closure_prob = predict_closure_risk(event_cause, corridor, zone, police_station,
                                         hour, dow, is_weekend, is_peak, authenticated, event_type, lat, lon)
    eta_min = get_eta_min(event_cause)
    fragility_score, is_named = get_fragility(corridor)
    diversion = suggest_diversion(corridor, zone) if is_named else None

    # Thresholds are calibrated to the actual OOF prediction distribution,
    # not arbitrary round numbers: base closure rate is 8.3%, so most
    # predictions cluster low (median 3.4%, 90th pct 18.7%). High = ~95th
    # percentile (0.35), Medium = ~80th percentile (0.12).
    if closure_prob >= 0.35:
        risk_label = 'High'
    elif closure_prob >= 0.12:
        risk_label = 'Medium'
    else:
        risk_label = 'Low'

    lines = []
    lines.append(f"Closure risk: {closure_prob*100:.0f}% ({risk_label})")
    lines.append(f"Estimated time to clear: ~{eta_min:.0f} minutes (historical median for '{event_cause}')")
    if is_named:
        lines.append(f"Corridor fragility score: {fragility_score:.1f}/10")
        if fragility_score >= 5:
            lines.append("This corridor is chronically vulnerable -- flag for infrastructure review.")
    else:
        lines.append("Not a named corridor -- no fragility history tracked for this road.")

    if risk_label == 'High':
        lines.append("Recommendation: dispatch a unit now, this is likely to require a closure.")
    elif risk_label == 'Medium':
        lines.append("Recommendation: monitor closely, prepare a unit on standby.")
    else:
        lines.append("Recommendation: log and monitor, no immediate dispatch needed.")

    if diversion:
        lines.append(f"Suggested diversion corridor(s) in {zone}: {', '.join(diversion)}")
    elif is_named:
        lines.append(f"No lower-fragility named corridor found in {zone} for diversion.")

    return {
        'closure_prob': closure_prob,
        'risk_label': risk_label,
        'eta_min': eta_min,
        'fragility_score': fragility_score,
        'is_named_corridor': is_named,
        'diversion': diversion,
        'message': '\n'.join(lines),
    }


if __name__ == '__main__':
    out = recommend(
        event_cause='vehicle_breakdown', corridor='Mysore Road', zone='Central Zone 2',
        police_station='Unknown', hour=18, dow=1, is_weekend=False, is_peak=True,
        authenticated=True, event_type='unplanned', lat=12.95, lon=77.55,
    )
    print(out['message'])
