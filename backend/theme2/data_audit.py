"""
Full dataset integrity audit -- checks that touch every row, not samples.
Run before trusting any model output downstream.
"""
import pandas as pd, numpy as np

DATA_PATH = r"c:\Users\BIT\Desktop\hackathon\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
df = pd.read_csv(DATA_PATH, low_memory=False)
print('shape:', df.shape)

print('\n--- 1. Duplicate rows ---')
print('duplicate id count:', df['id'].duplicated().sum())
print('fully duplicate rows:', df.duplicated().sum())

print('\n--- 2. Timestamp parsing (every row) ---')
st = pd.to_datetime(df['start_datetime'], errors='coerce', utc=True, format='mixed')
ct = pd.to_datetime(df['closed_datetime'], errors='coerce', utc=True, format='mixed')
print('start_datetime unparseable:', st.isnull().sum(), '/ raw null:', df['start_datetime'].isnull().sum())
print('closed_datetime unparseable (excl. legitimately missing):',
      (ct.isnull() & df['closed_datetime'].notna()).sum())

print('\n--- 3. Logical time consistency (every row with both timestamps) ---')
both = df.dropna(subset=['closed_datetime']).copy()
both['start_p'] = pd.to_datetime(both['start_datetime'], errors='coerce', utc=True, format='mixed')
both['closed_p'] = pd.to_datetime(both['closed_datetime'], errors='coerce', utc=True, format='mixed')
neg = both[both['closed_p'] <= both['start_p']]
print('rows where closed_datetime <= start_datetime:', len(neg))
if len(neg):
    print(neg[['id', 'event_cause', 'start_datetime', 'closed_datetime']].head(10).to_string(index=False))

print('\n--- 4. Geographic sanity (every row) ---')
# Bengaluru bounding box roughly lat 12.6-13.2, lon 77.3-77.9
bad_geo = df[~df['latitude'].between(12.0, 14.0) | ~df['longitude'].between(76.5, 78.5)]
print('rows with lat/lon outside greater-Bengaluru bbox:', len(bad_geo))
print('lat/lon == 0,0 rows:', ((df['latitude'] == 0) & (df['longitude'] == 0)).sum())
print('latitude null:', df['latitude'].isnull().sum(), '| longitude null:', df['longitude'].isnull().sum())

print('\n--- 5. Categorical value consistency (case/spelling dupes) ---')
for col in ['event_cause', 'event_type', 'status', 'priority', 'authenticated', 'corridor', 'zone']:
    vals = df[col].dropna().unique()
    lowered = pd.Series([str(v).lower().strip() for v in vals])
    dupes = lowered[lowered.duplicated()].unique()
    if len(dupes):
        print(f'{col}: possible case/whitespace duplicate categories ->', dupes.tolist())
    else:
        print(f'{col}: no case-duplicate categories ({len(vals)} unique)')

print('\n--- 6. requires_road_closure target integrity ---')
print('dtype:', df['requires_road_closure'].dtype)
print('unique values:', df['requires_road_closure'].unique())
print('null count:', df['requires_road_closure'].isnull().sum())

print('\n--- 7. authenticated / event_type binary integrity ---')
print('authenticated unique:', df['authenticated'].unique())
print('event_type unique:', df['event_type'].unique())

print('\n--- 8. client_id constant check (should not be used as a feature if constant) ---')
print('client_id unique values:', df['client_id'].nunique(), df['client_id'].unique()[:5])

print('\n--- 9. police_station / corridor / zone null counts ---')
print('police_station null:', df['police_station'].isnull().sum())
print('corridor null:', df['corridor'].isnull().sum())
print('zone null:', df['zone'].isnull().sum())

print('\n--- 10. id format consistency ---')
print('id matches FKID + 6 digits for all rows:', df['id'].str.match(r'^FKID\d{6}$').all())
