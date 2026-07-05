def build_kling_prompt(graph):

    text = """
Create a 40-60 second vertical cinematic video (9:16).

Maintain consistency of characters and environment.

STYLE: cinematic, realistic, business scenario
CAMERA: handheld documentary + slow push-ins

SCENES:
"""

    for s in graph:
        text += f"""
{ s['t'] } - { s['role'] }
Visual: { s['visual'] }
Camera: { s['camera'] }
"""

    return text