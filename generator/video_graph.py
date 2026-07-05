import re

def build_video_graph(scenario_text):

    def extract(section):
        match = re.search(f"{section}:(.*?)(?=(HOOK|TENSION|PAYOFF|CTA|$))", scenario_text, re.S)
        return match.group(1).strip() if match else ""

    return [
        {
            "t": "0-5s",
            "role": "hook",
            "visual": extract("HOOK"),
            "camera": "slow push-in"
        },
        {
            "t": "5-15s",
            "role": "tension",
            "visual": extract("TENSION"),
            "camera": "handheld shaky"
        },
        {
            "t": "15-30s",
            "role": "payoff",
            "visual": extract("PAYOFF"),
            "camera": "steady close-up"
        },
        {
            "t": "30-40s",
            "role": "cta",
            "visual": extract("CTA"),
            "camera": "static frame"
        }
    ]