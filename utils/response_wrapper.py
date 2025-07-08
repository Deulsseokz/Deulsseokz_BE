from rest_framework.response import Response

def api_response(is_success=True, code="COMMON200", message="성공입니다.", result=None, status=200): # default 값
    return Response({
        "isSuccess": is_success,
        "code": code,
        "message": message,
        "result": result,
    }, status=status)
