from rest_framework.response import Response

def api_response(is_success=True, code="COMMON200", message="성공입니다.", result=None, status_code=200, **kwargs):
    response = {
        "isSuccess": is_success,
        "code": code,
        "message": message,
        "result": result,
    }
    response.update(kwargs)  # count 같은 추가 키 포함
    return Response(response, status=status_code)
