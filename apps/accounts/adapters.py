from abc import ABC,abstractmethod
class GoogleIdentityVerifier(ABC):
    """Extension point for google-auth / OAuth provider integration."""
    @abstractmethod
    def verify(self,id_token:str)->dict: ...
