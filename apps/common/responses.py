from rest_framework.response import Response

def success(data=None, message="Success.", status=200):
    return Response({"success": True, "message": message, "data": {} if data is None else data}, status=status)
