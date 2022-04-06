import { ServerConnection } from "@jupyterlab/services";
import { CodeCellClient } from "./client";

// import $ = require("jquery");

export class BackendRequest {
    public static sendTrackPoint(type : String, description : String) {
        var request = {
            "type": "tracking",
            "track_type": type,
            "description": description,
        }
        new CodeCellClient()
        .request(
            "exec",
            "POST",
            JSON.stringify(request),
            ServerConnection.makeSettings()
        )
    }

    public static userInput(request : { [key: string] : any }, callback : Function = () => {}) {
        request["type"] = "user_input"
        new CodeCellClient()
        .request(
            "exec",
            "POST",
            JSON.stringify(request),
            ServerConnection.makeSettings()
        ).then((res) => {callback(res)})
    }
}