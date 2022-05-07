"""
RequestManager handles injesting and routing requests from the frontend
The actual information flow is

(init.py) post ==> RequestManager.handle_request ==> one of the routing codes

Then, the result from the function called by the route functions is returned
back to the original "post" function to respond to the frontend
"""
class RequestManager:
    def __init__(self, analysis_manager, tracking_manager):
        self.analysis_manager = analysis_manager
        self.tracking_manager = tracking_manager
        self.routeCodes = {
            # format:
            # [request type (str)] : [function which takes a JSON obj. parameter]
            "execute": analysis_manager.handle_execution,
            "tracking": tracking_manager.handle_track_request,
            "user_input": analysis_manager.handle_user_input
        }

    def handle_request(self, request):
        # given a request type, will execute the corresponding function
        return self.routeCodes[request["type"]](request)
