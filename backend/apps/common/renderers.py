from rest_framework.renderers import JSONRenderer
class EnvelopeJSONRenderer(JSONRenderer):
    def render(self,data,accepted_media_type=None,renderer_context=None):
        response=(renderer_context or {}).get("response")
        if data is not None and not (isinstance(data,dict) and "success" in data) and response is not None and response.status_code < 400:
            data={"success":True,"message":"Success.","data":data}
        return super().render(data,accepted_media_type,renderer_context)
