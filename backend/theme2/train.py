"""
Theme 2: Event-Driven Congestion - model training
Trains 2 supervised models on the Astram event dataset:
  1. closure risk    (binary classifier:  requires_road_closure)
  2. resolution time  (regressor:          minutes to clear, acute causes only, log1p target)
'priority' was evaluated and dropped -- it is ~100% determined by
corridor != "Non-corridor" (an administrative rule, not learned signal).
Also computes the corridor fragility index (heuristic aggregate, not ML).
Saves everything needed by the demo app into theme2/artifacts/.
"""
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, json, joblib, os
from sklearn.model_selection import StratifiedKFold, KFold
from sklearn.metrics import roc_auc_score, mean_absolute_error
import lightgbm as lgb

SEED, N_SPLITS = 42, 5
DATA_PATH = r"c:\Users\BIT\Desktop\hackathon\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
OUT_DIR = r"c:\Users\BIT\Desktop\hackathon\theme2\artifacts"
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(DATA_PATH, low_memory=False)
print('raw shape', df.shape)

for c in ['start_datetime', 'closed_datetime']:
    # format='mixed': the raw column mixes timestamps with and without
    # milliseconds (e.g. '...46+00' vs '...46.111+00'). Without this,
    # pandas infers one format and silently NaTs ~1.4% of rows -- which
    # turned out to be 69% closure-rate rows vs 8.3% baseline, i.e. NOT
    # random. format='mixed' parses every row correctly (verified: 0 NaT).
    df[c] = pd.to_datetime(df[c], errors='coerce', utc=True, format='mixed')

# ---------- feature engineering ----------
def fe(df):
    df = df.copy()
    df['hour'] = df['start_datetime'].dt.hour
    df['dow'] = df['start_datetime'].dt.dayofweek
    df['is_weekend'] = (df['dow'] >= 5).astype(int)
    # NOT generic rush-hour (8-9am/5-7pm) -- checked actual closure_rate by
    # hour: it's concentrated 10:00-17:00 (peaks at 40.7% at noon, 33.3% at
    # 16:00, 31.7% at 17:00) while textbook evening rush hours (19-22h) sit
    # at 5-7%, just high event *volume*, not high closure risk.
    df['is_peak'] = df['hour'].between(10, 17).astype(int)
    df['authenticated_bin'] = (df['authenticated'] == 'yes').astype(int)
    df['event_type_bin'] = (df['event_type'] == 'planned').astype(int)
    df['zone'] = df['zone'].fillna('Unknown')
    df['corridor'] = df['corridor'].fillna('Non-corridor')
    # 'Debris' (12 rows) and 'debris' (1 row) are the same category with
    # inconsistent casing -- verified via case-insensitive dupe check on
    # every unique event_cause value. Without this they'd fragment into
    # two separate one-hot/categorical codes for no real reason.
    df['event_cause'] = df['event_cause'].replace({'debris': 'Debris'})
    return df

df = fe(df)

CAT_COLS = ['event_cause', 'corridor', 'zone', 'police_station']
cat_maps = {}
for c in CAT_COLS:
    cats = df[c].astype('category').cat.categories
    cat_maps[c] = list(cats)
    df[c + '_code'] = pd.Categorical(df[c], categories=cats).codes

F = ['event_cause_code', 'corridor_code', 'zone_code', 'police_station_code',
     'hour', 'dow', 'is_weekend', 'is_peak', 'authenticated_bin', 'event_type_bin',
     'latitude', 'longitude']
CAT_IDX = [F.index(c + '_code') for c in CAT_COLS]

results = {}

# ---------- 1. closure risk classifier ----------
print('\n=== Closure risk classifier ===')
X = df[F]; y = df['requires_road_closure'].astype(int).values
oof = np.zeros(len(df))
skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
models_closure = []
for fold, (tr_i, va_i) in enumerate(skf.split(X, y)):
    m = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.03, num_leaves=63,
                            min_child_samples=10, colsample_bytree=0.8, subsample=0.9,
                            reg_alpha=0.1, reg_lambda=0.2, random_state=SEED, n_jobs=-1, verbose=-1)
    m.fit(X.iloc[tr_i], y[tr_i], categorical_feature=CAT_IDX,
          eval_set=[(X.iloc[va_i], y[va_i])], callbacks=[lgb.early_stopping(80, verbose=False)])
    oof[va_i] = m.predict_proba(X.iloc[va_i])[:, 1]
    models_closure.append(m)
    print(f'fold {fold+1}: AUC {roc_auc_score(y[va_i], oof[va_i]):.4f}')
auc = roc_auc_score(y, oof)
print(f'OOF AUC: {auc:.4f}')
results['closure_auc'] = auc
joblib.dump(models_closure, os.path.join(OUT_DIR, 'closure_models.pkl'))

# NOTE: 'priority' was tested as a classification target and dropped.
# It is ~100% determined by corridor != "Non-corridor" (an administrative
# rule, not learned severity) -- AUC 0.9998 was leakage, not signal.
# Kept as a documented finding for the pitch instead of a model.

# ---------- 2. resolution time (ETA) lookup ----------
print('\n=== Resolution time (ETA) ===')
# Scope to "acute" causes only -- pot_holes/road_conditions/water_logging/
# construction/Debris are maintenance tickets left open for weeks
# (median resolution 2,945-86,853 min) and don't represent an active
# road-clearance ETA. Acute causes resolve in 24 min - 12 hrs.
ACUTE_CAUSES = ['vehicle_breakdown', 'accident', 'tree_fall', 'congestion',
                 'procession', 'protest', 'vip_movement', 'public_event',
                 'Fog / Low Visibility']
res = df.dropna(subset=['closed_datetime']).copy()
res['resolution_min'] = (res['closed_datetime'] - res['start_datetime']).dt.total_seconds() / 60
res = res[res['event_cause'].isin(ACUTE_CAUSES)]
res = res[(res['resolution_min'] > 0) & (res['resolution_min'] < res['resolution_min'].quantile(0.95))]
print('rows with usable resolution time (acute causes only):', len(res))

# A LightGBM regressor was tried here first (log1p target, same CV setup as
# the other models). Result: OOF R2(log) = 0.08, MAE = 28.8 min, vs a naive
# "median resolution time per event_cause" baseline MAE = 29.4 min -- i.e.
# the model added essentially no lift over the simple historical median.
# ETA is not predictable from corridor/zone/time features beyond knowing
# the cause, so we use the transparent per-cause median lookup instead of
# a black-box model that doesn't actually add value.
eta_lookup = res.groupby('event_cause')['resolution_min'].median().rename('eta_min').reset_index()
print(eta_lookup.to_string(index=False))

# Fair (out-of-fold) baseline MAE -- fitting the per-cause median on train
# folds only and scoring on held-out folds, not an in-sample fit/score on
# the same rows. Confirms the "no lift over baseline" conclusion holds:
# OOF baseline MAE ~29.5 min, vs the LightGBM regressor's own OOF MAE of
# 28.8 min from the earlier comparison -- essentially the same.
res_idx = res.reset_index(drop=True)
kf_eta = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
oof_baseline = np.zeros(len(res_idx))
for tr_i, va_i in kf_eta.split(res_idx):
    fold_medians = res_idx.iloc[tr_i].groupby('event_cause')['resolution_min'].median()
    fold_global_median = res_idx.iloc[tr_i]['resolution_min'].median()
    oof_baseline[va_i] = res_idx.iloc[va_i]['event_cause'].map(fold_medians).fillna(fold_global_median).values
naive_mae = mean_absolute_error(res_idx['resolution_min'], oof_baseline)
results['eta_lookup_oof_mae_min'] = naive_mae
eta_lookup.to_csv(os.path.join(OUT_DIR, 'eta_lookup.csv'), index=False)

# ---------- corridor fragility index (heuristic aggregate) ----------
print('\n=== Corridor fragility index ===')
agg = df.groupby('corridor').agg(
    event_count=('id', 'count'),
    closure_rate=('requires_road_closure', 'mean'),
).reset_index()
res_by_corr = res.groupby('corridor')['resolution_min'].mean().rename('avg_resolution_min')
agg = agg.merge(res_by_corr, on='corridor', how='left')
agg['avg_resolution_min'] = agg['avg_resolution_min'].fillna(agg['avg_resolution_min'].median())

def norm(s):
    return (s - s.min()) / (s.max() - s.min() + 1e-9)

# "Non-corridor" is a catch-all bucket for thousands of unrelated local
# roads, not a real physical corridor -- it dominates ranking by sheer
# event_count but isn't a valid diversion target. Flag it out of the
# named-corridor ranking/heatmap rather than silently top-ranking it.
agg['is_named_corridor'] = agg['corridor'] != 'Non-corridor'

agg['fragility_score'] = (
    0.4 * norm(agg['event_count']) +
    0.4 * norm(agg['closure_rate']) +
    0.2 * norm(agg['avg_resolution_min'])
) * 10
agg = agg.sort_values('fragility_score', ascending=False).reset_index(drop=True)
print('Top named corridors by fragility:')
print(agg[agg['is_named_corridor']].head(10).to_string(index=False))
agg.to_csv(os.path.join(OUT_DIR, 'corridor_fragility.csv'), index=False)

# zone -> corridor mapping (most common *known* zone per corridor) for
# diversion suggestions. zone is 58% missing overall, so the mode must be
# taken over non-"Unknown" rows only -- otherwise "Unknown" wins for
# almost every corridor and diversion-by-zone breaks entirely.
def known_zone_mode(s):
    known = s[s != 'Unknown']
    if len(known) == 0:
        return 'Unknown'
    return known.mode().iat[0]

corridor_zone = df.groupby('corridor')['zone'].agg(known_zone_mode)
corridor_zone.to_csv(os.path.join(OUT_DIR, 'corridor_zone_map.csv'))

# ---------- save metadata for the demo app ----------
meta = {
    'features': F,
    'cat_cols': CAT_COLS,
    'cat_idx': CAT_IDX,
    'cat_maps': cat_maps,
    'metrics': results,
}
with open(os.path.join(OUT_DIR, 'meta.json'), 'w') as f:
    json.dump(meta, f, indent=2)

print('\nAll artifacts saved to', OUT_DIR)
print(json.dumps(results, indent=2))
