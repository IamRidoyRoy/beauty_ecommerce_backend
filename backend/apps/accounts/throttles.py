from rest_framework.throttling import SimpleRateThrottle
class AuthRateThrottle(SimpleRateThrottle):
    scope="auth"
    def get_cache_key(self,request,view):
        ident=(request.data.get("identifier") or request.data.get("phone") or "").strip().lower()
        return self.cache_format % {"scope":self.scope,"ident":f"{self.get_ident(request)}:{ident}"}
class OTPRateThrottle(SimpleRateThrottle):
    scope="otp"
    def get_cache_key(self,request,view):
        phone=(request.data.get("phone") or "").strip()
        return self.cache_format % {"scope":self.scope,"ident":f"{self.get_ident(request)}:{phone}"}
