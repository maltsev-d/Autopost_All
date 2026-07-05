import random

def build_blueprint(data):
    return {
        "process": random.choice(data["processes"]),
        "problem": random.choice(data["problems"]),
        "situation": random.choice(data["situations"]),
        "solution": random.choice(data["solutions"])
    }