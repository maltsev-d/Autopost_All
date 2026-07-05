import pandas as pd

def load_excel(path):
    df = pd.read_excel(path)

    return df.to_dict(orient="records")