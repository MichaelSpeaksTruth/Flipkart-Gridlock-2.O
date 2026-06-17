"""
Theme 2: model comparison for the closure-risk classifier.
Same CV folds, same features, different algorithms -- to check whether
LightGBM is actually the best choice or just the default we reached for.
"""
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from catboost import CatBoostClassifier
import lightgbm as lgb

DATA_PATH = r"c:\Users\BIT\Desktop\hackathon\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
SEED, N_SPLITS = 42, 5

df = pd.read_csv(DATA_PATH, low_memory=False)
df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce', utc=True, format='mixed')
df['hour'] = df['start_datetime'].dt.hour
df['dow'] = df['start_datetime'].dt.dayofweek
df['is_weekend'] = (df['dow'] >= 5).astype(int)
df['is_peak'] = df['hour'].isin([8, 9, 17, 18, 19]).astype(int)
df['authenticated_bin'] = (df['authenticated'] == 'yes').astype(int)
df['event_type_bin'] = (df['event_type'] == 'planned').astype(int)
df['zone'] = df['zone'].fillna('Unknown')
df['corridor'] = df['corridor'].fillna('Non-corridor')
df['latitude'] = df['latitude'].fillna(df['latitude'].median())
df['longitude'] = df['longitude'].fillna(df['longitude'].median())

CAT_COLS = ['event_cause', 'corridor', 'zone', 'police_station']
for c in CAT_COLS:
    cats = df[c].astype('category').cat.categories
    df[c + '_code'] = pd.Categorical(df[c], categories=cats).codes

F = ['event_cause_code', 'corridor_code', 'zone_code', 'police_station_code',
     'hour', 'dow', 'is_weekend', 'is_peak', 'authenticated_bin', 'event_type_bin',
     'latitude', 'longitude']
CAT_IDX = [F.index(c + '_code') for c in CAT_COLS]
X = df[F]; y = df['requires_road_closure'].astype(int).values
skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)


def cv_auc_tree(make_model, cat_param=None):
    oof = np.zeros(len(X))
    for tr_i, va_i in skf.split(X, y):
        Xtr, Xva = X.iloc[tr_i], X.iloc[va_i]
        m = make_model()
        if cat_param == 'lgb':
            m.fit(Xtr, y[tr_i], categorical_feature=CAT_IDX)
        elif cat_param == 'catboost':
            m.fit(Xtr, y[tr_i], cat_features=CAT_IDX, eval_set=(Xva, y[va_i]), verbose=False)
        else:
            m.fit(Xtr, y[tr_i])
        oof[va_i] = m.predict_proba(Xva)[:, 1]
    return roc_auc_score(y, oof)


def cv_auc_onehot(make_model):
    oof = np.zeros(len(X))
    for tr_i, va_i in skf.split(X, y):
        full = pd.get_dummies(X, columns=[F[i] for i in CAT_IDX])
        Xtr2, Xva2 = full.iloc[tr_i], full.iloc[va_i]
        m = make_model()
        m.fit(Xtr2, y[tr_i])
        oof[va_i] = m.predict_proba(Xva2)[:, 1]
    return roc_auc_score(y, oof)


results = {}

def run(name, fn):
    auc = fn()
    results[name] = auc
    print(f'{name:30s} {auc:.4f}')

run('LightGBM', lambda: cv_auc_tree(
    lambda: lgb.LGBMClassifier(n_estimators=500, learning_rate=0.03, num_leaves=31,
                                random_state=SEED, verbose=-1), cat_param='lgb'))
run('CatBoost', lambda: cv_auc_tree(
    lambda: CatBoostClassifier(iterations=500, depth=6, random_seed=SEED, verbose=False),
    cat_param='catboost'))
run('RandomForest', lambda: cv_auc_tree(
    lambda: RandomForestClassifier(n_estimators=500, max_depth=8, random_state=SEED, n_jobs=-1)))
run('ExtraTrees', lambda: cv_auc_tree(
    lambda: ExtraTreesClassifier(n_estimators=500, max_depth=8, random_state=SEED, n_jobs=-1)))
run('LogisticRegression (one-hot)', lambda: cv_auc_onehot(
    lambda: LogisticRegression(max_iter=2000, C=1.0)))

print('\n=== Closure-risk model comparison (5-fold OOF AUC), sorted ===')
for name, auc in sorted(results.items(), key=lambda kv: -kv[1]):
    print(f'{name:30s} {auc:.4f}')
