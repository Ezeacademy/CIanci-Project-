import hashlib

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class PasswordResetIPThrottle(AnonRateThrottle):
    scope = "password_reset_ip"


class PasswordResetEmailThrottle(SimpleRateThrottle):
    scope = "password_reset_email"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        if not isinstance(email, str) or not email.strip():
            return None
        digest = hashlib.sha256(email.strip().casefold().encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class VerificationResendThrottle(SimpleRateThrottle):
    scope = "verification_resend"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }
