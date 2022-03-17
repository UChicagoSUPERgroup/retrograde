// Jupyter imports
import { JupyterFrontEnd } from "@jupyterlab/application";
import { INotebookTracker, NotebookPanel } from "@jupyterlab/notebook";

// PromptML plugin imports
import { Listener } from "./cell-listener";

// PromptML frontend components
import { PopupNotification } from "./components/PopupNotification";
import { ProtectedColumnNote } from "./components/ProtectedColumnNote";
import { WelcomeNote } from "./components/WelcomeNote";
import { Group } from "./components/Group";
import { Model } from "./components/Model";

// Dependency imports
import $ = require("jquery");
import deepEqual = require("fast-deep-equal")

interface ProxyColumnRelationships {
  predictive: string[];
  correlated: string[];
  pvals: string[];
  coeffs: string[];
}

export class Prompter {
  // Maintains a list of previously-sent information
  // Distinct from the index.ts `openNotes` as this stores content -- not
  // information about the DOM node itself.
  // Structure:
  // oldContent = {
  //     <String type of notification> : <String content of the notification> 
  // }
  oldContent: { [key: string]: any[] }
  // Holds a pointer to an index.ts function that is able to manipulate
  // the content of open notifications on the frontend.
  // Validation checks for open / closed notifications are handled by index.ts
  notificationUpdate: Function
  // This generates prompts for notebook cells on notification of new data or a new model
  constructor(
    listener: Listener,
    tracker: INotebookTracker,
    app: JupyterFrontEnd,
    factory: NotebookPanel.IContentFactory,
    notificationUpdate: Function // holds the pointer to the `onUpdate` index.ts function
  ) {
    this.oldContent = {}; // see structure above

    // This function is executed whenever new information is received from
    // the backend but a notification has already been generated
    this.notificationUpdate = notificationUpdate;
    
    // Handler for the backend JSON object of notifications to generate
    listener.infoSignal.connect((sender: Listener, output: any) => {
      this._onInfo(output);
    });
  }

  // Compares two messages received from the backend to determine if the frontend
  // should show that new information is avaiable.
  // Message format (for both):
  // Msg: [
  //    {
  //      "type": <note type>,
  //      <note key string> : <any possible value including an object>
  //    },
  //    ... more notes
  // ]
  // One "message" is the list of notes generated by the backend for one note
  private _isMessageDifferent(msg : { string : any }[], oldMsg : {string : any}[]) {
    // If there is a new note generated, then there will be new information and we
    // don't have to check each individually
    if(msg.length != oldMsg.length) {
      return true
    }
    // Iterates over each note within the array to see if its content has changed
    for(var x = 0; x < msg.length; x++) {
      if(!deepEqual(msg[x], oldMsg[x])) {
        return true;
      }
    }
    // Notes are exactly the same
    return false
  }
  
  // Converts the PopupNotification export format to a type-script allowed
  // version for appending to the JupyterLab interface
  private _appendNote(note: any) {
    this._appendMsg((note[0] as HTMLDivElement).outerHTML, note[1]);
  }

  // Takes a new notification to generate and
  // (1) checks if it needs to be added to the page
  // (2) attaches event listeners for user interactions
  // (3) Attempts to update existing content
  // (4) OR append the notification to the UI
  private _appendMsg(msg: string, handedPayload: any) {
    var newNote = $.parseHTML(msg);
    // Check if this note has been received by the plugin before
    if("typeOfNote" in handedPayload && handedPayload["typeOfNote"] in this.oldContent) {
      // If it's already been rendered, try to update the content of the open view.
      // index.ts checks if the notification exists -- we don't need to handle that here
      this.notificationUpdate(handedPayload, handedPayload["typeOfNote"]);
      // If the message is different, then we want to remove the "clicked" styling of the note,
      // signaling to the user that there is new information
      if(this._isMessageDifferent(handedPayload["originalMessage"], this.oldContent[handedPayload["typeOfNote"]])) {
        console.log(handedPayload["typeOfNote"], "has changed content and needs a visual refresh, continuing with generating new note")
      } else {
        // The message is the same, so allow the current "clicked" notification to remain
        return
      }
    }
    // Record what notifications have been sent (most recent version)
    this.oldContent[handedPayload["typeOfNote"]] = handedPayload["originalMessage"];
    // Add the note the popup interface
    $(".prompt-ml-container").prepend(newNote);
    // Add handling for the note being expanded 
    $(newNote).on("mouseup", function () {
      $(this).find(".note").addClass("note-clicked"); // visually indicates it has been clicked
      // Prepares event data; if the note is clicked, index.ts manages opening up a new window
      // and rendering the new content.
      // To see what data is sent, look at the export method in PopupNotification.ts
      if (handedPayload == {}) { // default case
        var payload: object = {
          title: "Default Page",
          htmlContent: $.parseHTML("<h1>This note failed to generate.</h1>"),
          originalMessage: {}
        };
      } else {
        payload = handedPayload;
      }
      $(".prompt-ml-container").trigger("prompt-ml:note-added", {
        payload: payload,
      });
    });
    // Iterate over existing notes and ensure that repetitive
    // notes are removed from the interface
    var divs = $(".prompt-ml-container > div");
    for (var x = 0; x < divs.length; x++) {
      var targetDiv = divs[x];
      if ($(newNote).is($(targetDiv))) continue;
      if ($(targetDiv).text() == $(newNote).text()) {
        $(targetDiv).remove();
      }
    }
  }

  // Main notification handling function
  private _onInfo(info_object: any) {
    var kernel_id = info_object["kernel_id"];
    console.log("_onInfo");
    for (const notice_type in info_object) {
      var list_of_notes = info_object[notice_type];
      switch(notice_type) {
        case "proxy":
          this._handleProxies(list_of_notes);
          break;
        case "error":
          this._makeErrorMessage(list_of_notes);
          break;
        case "resemble":
          this._makeResembleMsg(list_of_notes, String(kernel_id));
          break;
        case "missing":
          this._handleMissing(list_of_notes);
          break;
        case "model_report":
          this._makeEqOdds(list_of_notes);
          break;
        case "welcome":
          this._makeWelcomeMsg();
          break;
        default:
          console.log(`Note type not recognized, ${notice_type}`);
      }
    }      
  }

  private _makeWelcomeMsg() {
    var note = new WelcomeNote()
    console.log("generating welcome")
    this._appendNote(note.generateFormattedOutput())
  }

  private _makeEqOdds(eqOdds: { [key: string]: any }[]) {
    var note = new PopupNotification("modelReport", false, "Model Report Note", eqOdds);
    note.addHeader("Model Report Note")
    console.log("eqodds length ",eqOdds.length); 
    // preamble on MRN
    note.addParagraph(`<p><b>The Model Report Note</b> uses the sensitivity as marked in the Protected Column Note to determine
                       the columns that will be considered in this model report. By parsing your code, the plugin is able to find the original dataframe
                       your test dataframe was derived from and uses the sensitive columns found in that dataframe to measure
                       your model's performance across groups you may have excluded in your test features.</p>`);
    // <p style="color:green"><i>${metric_name}: ${metric}</i></p>
    note.addParagraph(`<br /><p> <span style="color:green"><i>"metric_name": "metric_value"</i></span> indicates that a metric is performing some percent better than the median for that group while
                       <span style="color:red"><b>"metric_name": "metric_value"</b></span> does the same for metrics performing some percent worse than the median for that group.</p>`)
    for(var m = 0; m < eqOdds.length; m++) {
      var model : { [key: string] : any} = eqOdds[m];
      console.log("eqodds model ", model["model_name"], "m ",m);
      // Name and accuracy to the first decimal place (i.e. 10.3%)
      var name = "Model " + model["model_name"] + " (" + (Math.floor(1000 * model["acc_orig"]) / 10) + "% accuracy)"
      var groups : Group[] = []
      for(var group in model["k_highest_error_rates"]) {
        for(var correspondingGroup in model["k_highest_error_rates"][group]) {
          var thisGroup = model["k_highest_error_rates"][group][correspondingGroup]["metrics"];
          // Round to 3 decimal places
          // To do: dedicated rounding method / global rounding config setting
          for(var x = 0; x < thisGroup.length; x++)
            thisGroup[x] = Math.floor(model["k_highest_error_rates"][group][correspondingGroup]["metrics"][x] * 1000) / 1000
          // Backend sends information in a static, predefined order
          var precision : string = thisGroup[0],
          recall = thisGroup[1],
          f1score = thisGroup[2],
          fpr = thisGroup[3],
          fnr = thisGroup[4],
          count = thisGroup[5];
          console.log(model["k_highest_error_rates"][group][correspondingGroup]["highlight"]);
          var highlights : number[] = model["k_highest_error_rates"][group][correspondingGroup]["highlight"];

          groups.push(new Group(group+": "+correspondingGroup, precision, recall, f1score, fpr, fnr, count, highlights))
        }
      }
      // Attaching the data to the note itself
      note.addRawHtmlElement(new Model(name, model["current_df"], model["ancestor_df"], groups).export())
    }
    note.addParagraph(`<p>This plugin has calculated performance metrics for data subsets based on Protected Columns</p>`);
    note.addParagraph(`<br /><p><b>Why it matters</b> Overall accuracy of a model may not tell the whole story. 
                       A model may be accurate overall, but may have better or worse performance on particular data subsets. 
                       Alternatively, errors of one type may be more frequent within one subset, and errors of another type may be more frequent in a different data subset.</p>`);
    
    note.addParagraph(`<br /><p><b>What you can do</b> It is up to you to determine how to balance overall accuracy and group-level performance. 
                     It may be the case that choosing a different model, choosing different model parameters, or choosing different input columns will change these characteristics.
                Exploring the whole space may not be feasible, so prioritizing certain performance metrics and groups, and characterizing the tradeoffs there may be most efficient.</p>`);
    note.addParagraph(`<br /><p><b>How was it detected?</b> The performance metrics shown here are derived from the plugin's best guess at the protected columns associated with the model's testing data. 
                       Because of this they may not perfectly match a manual evaluation. 
                       The plugin calculates the performance with respect to protected groups identified in the Protected Column note. 
                       The plugin calculates precision, recall, F1 Score, false positive rate (FPR) and false negative rate (FNR). More information about these metrics can be found <a style="color:blue" href="https://towardsdatascience.com/performance-metrics-confusion-matrix-precision-recall-and-f1-score-a8fe076a2262">here</a></p>`);
    // Send to the Jupyterlab interface to render
    var message = note.generateFormattedOutput();
    this._appendNote(message);
  }

  private _handleProxies(
    proxies: { [key: string]: any }[],
  ) {
    var d: { [key: string]: { [key: string]: string[] } } = {};
    for (var x = 0; x < proxies.length; x++) {
      var p: any = proxies[x];
      if (!(p["df"] in d))
        d[p["df"]] = { proxy_col_name: [], sensitive_col_name: [], p_vals: [], pearsons: [] };
        d[p["df"]]["proxy_col_name"].push(p["proxy_col_name"]);
        d[p["df"]]["sensitive_col_name"].push(p["sensitive_col_name"]);
        d[p["df"]]["p_vals"].push(p["p"]);
        d[p["df"]]["pearsons"].push(p["coefficient"]);
    }
    var message = this._makeProxyMsg(d);
    this._appendNote(message);
  }

  private _handleMissing(
    missing_notes: { [key: string] : any}[],
  ) {
    var note = this._makeMissingMsg(missing_notes);
    var message = note.generateFormattedOutput();
    this._appendNote(message);
  }

  // To check
  private _makeResembleMsg(
    notices: any[],
    kernel_id: string
  ) {
    var note = new ProtectedColumnNote(notices, kernel_id, notices);
    var message = note.generateFormattedOutput();
    this._appendNote(message);
  }

  private _makeProxyMsg(d: any) {
    var note = new PopupNotification("proxy", false, "Proxy Columns", d);
    note.addHeader("Proxy Columns");

    for (let df_name in d) {
      note.addHeader(`Within <span class="code-snippet">${df_name}</span></strong>`);
      var df = d[df_name];
      const columnNames = df["sensitive_col_name"];
      const tableRows: { [columnName: string]: ProxyColumnRelationships } = {};
      columnNames.forEach((columnName: string, idx: number) => {
        if (tableRows[columnName] === undefined) {
          tableRows[columnName] = {
            predictive: [],
            correlated: [],
            pvals: [],
            coeffs: []
          };
        }
        if (df["p_vals"][idx] < 0.001) {
          tableRows[columnName].correlated.push(df["proxy_col_name"][idx]);
        } else {
          tableRows[columnName].predictive.push(df["proxy_col_name"][idx]);
        }
        tableRows[columnName].pvals.push(df["p"][idx]);
        tableRows[columnName].coeffs.push(df["coefficient"][idx]);
      });
      const tableHeader = `
        <thead>
          <tr>
            <th>Column name</th>
            <th>Highest correlated columns</th>
            <th>p-value</th>
            <th>Pearson coefficient</th>
            <th>Other correlated columns</th>
          </tr>
        </thead>
      `;
      const tableEntries = Object.entries(tableRows).map(
        ([columnName, relationships]) => {
          const predictiveFeatures =
            relationships.predictive.length > 0
              ? relationships.predictive.join(", ")
              : " ";
          const correlatedFeatures =
            relationships.correlated.length > 0
              ? relationships.correlated.join(", ")
              : " ";
          const pValues = relationships.pvals.length > 0
            ? relationships.pvals.join(", ")
            : " ";
          const pearsonCoefficients = relationships.coeffs.length > 0
            ? relationships.coeffs.join(", ")
            : " ";
          return `
          <tbody>
              <tr>
                  <td>${columnName}</td>
                  <td>${predictiveFeatures}</td>
                  <td>${pValues}</td>
                  <td>${pearsonCoefficients}</td>
                  <td>${correlatedFeatures}</td>
              </tr>
          </tbody>
          `;
        }
      );

      const fullTable = $.parseHTML(
        `<div class="proxy-columns-table"><table>${tableHeader}${tableEntries.join("")}</table></div>`
      );
      const fullTableHtmlElement = fullTable[0] as any as HTMLElement;
      note.addRawHtmlElement(fullTableHtmlElement);
    }


    const description = $.parseHTML(
      "<div>" +
        "<br /><p>This plugin has detected the presence of certain columns in this notebook that are correlated with sensitive variables.</p>" +
        '<br /><p><b>Why it matters</b> Using columns correlated with sensitive variables may produce outcomes that are biased. This bias may be undesirable, unethical and in some cases illegal. </p>' +
        "<br /><p><b>What you can do</b> The correlations found or suggested here may or may not be meaningful. There also may be situation-specific correlations that are not detected by this plugin. In some cases, it may be appropriate to use a column which does have a correlation with a sensitive variable.</p>" +
        "<br /><p>Ultimately, it is up to you to make a decision about whether it is valid to include the correlated columns in your model.</p>"+
        "<br /><p><b>How was it detected?</b> The plugin calculates these values by comparing every sensitive column with every non-sensitive column. The plugin uses Analysis of Variance, Chi-Square, and Spearman tests depending on the type of columns being compared." + 
        "The correlations shown are those that had a p-value of less than 0.2, the Highest Correlated columns are those that had a p-value of less than 0.001"+
        "</div>"
    );
    const descriptionHtmlElement = description[0] as any as HTMLElement;
    note.addRawHtmlElement(descriptionHtmlElement);


    return note.generateFormattedOutput();
  }

  private _makeMissingMsg(
    notice: { [key: string]: any }[],
  ) {
    var note: PopupNotification = new PopupNotification(
      "missing",
      false,
      "Missing Data",
      notice
    );
    note.addHeader("Missing Data");
    for (var df_idx in notice) {
      // Small-view df container
      var df_name = notice[df_idx]["df"];
      note.addSubheader(`<h3>Within <span class="code-snippet">${df_name}</span></h3>`);
      var ul = [];
      // Expanded-view df container
      // Iterating over every column
      var df = notice[df_idx]; 
      for (const col_name_index in df["missing_columns"]) {
        // Extract information for the small-view content
        console.log("colname index ",col_name_index);
        var col_count = df["missing_columns"][col_name_index]["number_missing"];
        var total_length = df["missing_columns"][col_name_index]["total_length"];
        // Extract the mode (for expanded view)
        var modes = [];
        console.log("extracting view ", df["missing_columns"][col_name_index]);
        for (const key in df["missing_columns"][col_name_index]["sens_col"]) {
          console.log("key ",key);
          modes.push([key, df["missing_columns"][col_name_index]["sens_col"][key]["largest_percent"]]);
        }
        modes = modes.sort(
          (a: [string, number][][], b: [string, number][][]) => {
            if (a[1] === b[1]) {
              return 0;
            } else {
              return a[1] > b[1] ? -1 : 1;
            }
          }
        );
        if (modes.length == 0) {
          continue;
        }
        console.log("modes", modes);
        var cor_col = modes[0][0];
        var cor_mode = df["missing_columns"][col_name_index]["sens_col"][cor_col]["largest_missing_value"];
        var num_missing = df["missing_columns"][col_name_index]["sens_col"][cor_col]["n_missing"];
        var num_max = df["missing_columns"][col_name_index]["sens_col"][cor_col]["n_max"];

        ul.push(
          `When <strong>${cor_col}</strong> is <strong>${cor_mode}</strong>, <strong>${col_name_index}</strong> is missing <strong>${num_missing}</strong>/<strong>${num_max}</strong> entries`
        );
        ul.push([
          `${col_name_index} is missing ${col_count}/${total_length} entries`,
        ]);
      }
      note.addList(ul);
    }
    note.addParagraph("This plugin has detected patterns of missing data");
    note.addParagraph(`<br /><b>Why it matters</b> There are a number of reasons why data may be missing. In some instances, 
    it may be due to biased collection practices. It may also be missing due to random 
    error.  How you handle the missing values may impact how the model behaves.`);

    note.addParagraph(`<br /><b>What you can do</b> It is up to you to determine why you think the values in each column are missing.
    In some cases, it may be appropriate to exclude rows with missing entries in a particular column.
    It may also be appropriate to impute that data. These decisions also may depend on whether you believe the column is relevant to the predictive
    task. If the column with missing data is not relevant, then it may be appropriate to exclude that column.`)

    note.addParagraph(`<br /><b>How was it detected?</b> The plugin calculates missing data values by examining the all columns with na values. 
    This means that placeholder values not recognized by <code>pd.isna()</code> are not recognized.
    This note uses the protected columns identified in the Protected Column notification and checks the most common sensitive data value when an entry is missing.
    It does not check combinations of columns.`);
    // Create container for the small-view content
    // Iterating over every dataframe
    return note;
  }

  private _makeErrorMessage(
    notices: { [key: string]: any }[],
  ) {
    var note = new PopupNotification("errors", false, "Errors", notices);
    note.addHeader("Errors");
    // Consolidating the notes sent to the frontend into a usable dictionary
    // The received data is a list of individual objects, with formats such as
    // {
    //    metric_in: 0.5555555555555556,
    //    metric_name: "fpr",
    //    metric_out: 0.38461538461538464,
    //    model_name: "dt",
    //    n: 21,
    //    neg_value: "True",
    //    pos_value: "False",
    //    slice: {
    //      ['interest', '(7.22, 9.557]'],
    //      ['type_home', '0']
    //    }
    // }
    // However, the final list of sorted first by models and then by metrics. Therefore,
    // we want a format more similar to
    // {
    //   "lr": {
    //      "fpr": [
    //        "metric_in": ...,
    //        ...
    //       ],
    //      "fnr": [
    //        "metric_in": ...,
    //        ...
    //      ]
    //   },
    //   (other models)
    // }
    var models: { [key: string]: any } = {};
    for (var x = 0; x < notices.length; x++) {
      var notice = notices[x];
      if (!(notice["model_name"] in models))
        models[notice["model_name"]] = {
          fpr: [],
          fnr: [],
        };
      models[notice["model_name"]][notice["metric_name"]].push({
        slice: notice["slice"],
        count: notice["n"],
        metric_in: notice["metric_in"],
        metric_out: notice["metric_out"],
        pos_value: notice["pos_value"],
        neg_value: notice["neg_value"],
      });
    }
    // Generating the dynamic content
    for (var model_name in models) {
      var model_notes = models[model_name];
      if (model_notes["fpr"].length == 0 || model_notes["fnr"].length == 0)
        continue;
      var fprString = this._makeErrorNoteLists(
        model_notes["fpr"],
        `Assuming ${model_notes["fpr"][0]["pos_value"]} given the true value of ${model_notes["fpr"][0]["neg_value"]}`
      );
      var fnrString = this._makeErrorNoteLists(
        model_notes["fnr"],
        `Assuming ${model_notes["fnr"][0]["neg_value"]} given the true value of ${model_notes["fnr"][0]["neg_value"]}`
      );
      note.addList([
        `In the model ${model_name}, there was an unusually high probability of:`,
        [fprString, fnrString],
      ]);
    }
    // Adding static content; creating response object
    var message = note.generateFormattedOutput();
    this._appendNote(message);
  }

  // Takes in a list of slice objects with metric / positive value / negative value information
  private _makeErrorNoteLists(
    segments: { [key: string]: any }[],
    metricName: string
  ) {
    // Creating an HTML string that visually represents the object created at the beginning
    // of _makeErrorMessages. The data that is passed in is the list of objects (accessible
    // through the "fnr" / "fpr" of the models object)
    var returnArray: any = [metricName, []];
    for (var x = 0; x < segments.length; x++) {
      // Slices are represented as an array, so we iterate over them to combine into a single string
      // var sliceString = "<li>";
      var sliceString = "";
      for (var y = 0; y < segments[x]["slice"].length; y++) {
        sliceString += `${segments[x]["slice"][y][0]}: ${segments[x]["slice"][y][1]}`;
        if (y != segments[x]["slice"].length - 1) sliceString += ", ";
      }
      returnArray[1].push(sliceString);
      returnArray[1].push([
        `Slice size was ${segments[x]["count"]}. The outside metric is ${
          Math.floor(segments[x]["metric_out"] * 100) / 100
        }. The inside metric is ${
          Math.floor(100 * segments[x]["metric_in"]) / 100
        }.`,
      ]);
    }
    return returnArray;
  }
}
