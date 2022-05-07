class TrackingManager:
    def __init__(self, app, database_manager):
        self._nb = app
        self.database_manager = database_manager

    def handle_track_request(self, request):
        self._nb.log.info(("[TRACKING] Adding track of type {0} and description \"{1}\"").format(request["track_type"], request["description"]))
        self.addTrack(request["track_type"], request["description"])
        return

    def addTrack(self, track_type, description):
        self.db().addTrack(track_type, description)

    def db(self):
        return self.database_manager.getDb()