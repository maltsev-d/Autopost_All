def build_scenario_mistral(row, mistral_call):

    prompt = f"""
You are a strict video script generator.

Return ONLY this format:

HOOK:
...
TENSION:
...
PAYOFF:
...
CTA:
...

Rules:
- no extra text
- no explanations
- short sentences
- cinematic tone

Context:
Industry: {row.get('industry')}
Problem: {row.get('problem')}
Situation: {row.get('situation')}
Solution: {row.get('solution')}
"""

    return mistral_call(prompt)