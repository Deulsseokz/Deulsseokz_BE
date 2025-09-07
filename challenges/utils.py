import re

# 장소-챌린지 조건 추출
def extract_conditions(*conditions):
    extracted = []
    for cond in conditions:
        matches = re.findall(r'\[(.*?)\]', cond)
        extracted.extend(matches)
    return extracted