import pandas as pd
from llm import ask_llm
from prompt import build_prompt

df = pd.read_excel("content.xlsx")

row = df.iloc[0].to_dict()

prompt = build_prompt(row)

result = ask_llm(prompt)

print("\n===== KLING OUTPUT =====\n")
print(result)

with open("output.txt", "w", encoding="utf-8") as f:
    f.write(result)