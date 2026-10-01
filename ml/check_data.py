import pandas as pd
import os

data_dir = "data/raw"
files = os.listdir(data_dir)

for f in files:
    if f.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_dir, f), nrows=5)
        print(f"\n{'='*60}")
        print(f"File: {f}")
        print(f"Columns: {len(df.columns)}")
        print(df[' Label'].value_counts() if ' Label' in df.columns else "No Label column")