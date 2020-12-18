import { URLExt } from "@jupyterlab/coreutils";
import { ServerConnection } from "@jupyterlab/services";
import { Constants } from "./constants";

export class CodeCellClient {
  public request(
    path: string, method: string, body: any, 
    settings: ServerConnection.ISettings): Promise<any> {

    const fullUrl = URLExt.join(
      settings.baseUrl,
      Constants.SHORT_PLUGIN_NAME,
      path
    );
    return ServerConnection.makeRequest(
      fullUrl,
      { body, method },
      settings
    ).then(response => {
      if (response.status !== 200) {
        return response.text().then(data => {
          throw new ServerConnection.ResponseError(response, data);
        });
      }
      return response.text();
    });
  }
}
