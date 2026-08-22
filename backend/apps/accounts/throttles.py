from rest_framework.throttling import SimpleRateThrottle


class AuthRateThrottle(SimpleRateThrottle):
    scope = "auth"

    def get_cache_key(self, request, view):
        ident = (request.data.get("identifier") or request.data.get("phone") or "").strip().lower()
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{ident}"}


class OTPRateThrottle(SimpleRateThrottle):
    scope = "otp"

    def parse_rate(self, rate):
        # DRF's stock parser supports `5/min`, `20/hour`, etc., but it does not
        # understand numeric windows such as `5/10min`; it attempts to use the
        # first character (`1`) as a duration key and raises KeyError('1').
        # Keep the human-friendly setting while supporting an exact 10-minute
        # window here.
        if rate:
            try:
                count, period = rate.split("/", 1)
            except ValueError:
                pass
            else:
                normalized = period.strip().lower()
                numeric_periods = {
                    "10min": 600,
                    "10mins": 600,
                    "10minute": 600,
                    "10minutes": 600,
                }
                if normalized in numeric_periods:
                    return int(count), numeric_periods[normalized]
        return super().parse_rate(rate)

    def get_cache_key(self, request, view):
        phone = (request.data.get("phone") or "").strip()
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{phone}"}
