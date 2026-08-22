from abc import ABC,abstractmethod
from rest_framework.exceptions import ValidationError
class CourierAdapter(ABC):
    @abstractmethod
    def create_shipment(self,order): ...
    @abstractmethod
    def cancel_shipment(self,shipment): ...
    @abstractmethod
    def track(self,shipment): ...
class PathaoAdapter(CourierAdapter):
    def create_shipment(self,order): raise NotImplementedError("Configure Pathao credentials and API client.")
    def cancel_shipment(self,shipment): raise NotImplementedError
    def track(self,shipment): raise NotImplementedError
class SteadfastAdapter(PathaoAdapter): pass
class RedXAdapter(PathaoAdapter): pass
