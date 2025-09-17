import re

def extract_conditions(challenge):
    """
    Challenge 객체를 받아 condition 필드들에서
    대괄호([]) 안의 키워드만 추출하여 리스트로 반환합니다.
    """
    extracted_keywords = []

    condition_fields = [
        challenge.condition1,
        challenge.condition2,
        challenge.condition3
    ]

    for condition_text in condition_fields:
        # 필드 값이 비어있지 않은 경우(None이나 빈 문자열이 아닐 때)에만 실행
        if condition_text:
            # 정규표현식을 사용하여 대괄호 안의 내용을 찾음
            match = re.search(r'\[(.*?)\]', condition_text)
            if match:
                # 찾은 키워드를 리스트에 추가
                keyword = match.group(1)
                extracted_keywords.append(keyword)
    
    return extracted_keywords