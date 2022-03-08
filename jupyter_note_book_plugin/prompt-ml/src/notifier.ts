import { JupyterFrontEnd } from "@jupyterlab/application";

import { INotebookTracker, NotebookPanel } from "@jupyterlab/notebook";

import { Listener } from "./cell-listener";

import { PopupNotification } from "./components/PopupNotification";
import { ProtectedColumnNote } from "./components/ProtectedColumnNote";
import { Group } from "./components/Group";
import { Model } from "./components/Model";

import $ = require("jquery");

// Global used to construct unique ID's
// This is increased by 1 everytime that a group of notifications is received by the frontend
// Allows us to have a unique ID for every notification so that repeat notes will open the same widget
var global_notification_count: number = 0;

interface ProxyColumnRelationships {
  predictive: string[];
  correlated: string[];
}

export class Prompter {
  // This generates prompts for notebook cells on notification of new data or a new model
  constructor(
    listener: Listener,
    tracker: INotebookTracker,
    app: JupyterFrontEnd,
    factory: NotebookPanel.IContentFactory
  ) {
    listener.infoSignal.connect((sender: Listener, output: any) => {
      this._onInfo(output);
    });
  }

  private _appendNote(note: any) {
    console.log(note);
    this._appendMsg((note[0] as HTMLDivElement).outerHTML, note[1]);
  }

  private _appendMsg(msg: string, handedPayload: any) {
    var newNote = $.parseHTML(msg);
    $(".prompt-ml-container").prepend(newNote);
    $(newNote).on("mouseup", function () {
      if (handedPayload == {}) {
        var payload: object = {
          title: "Default Page",
          htmlContent: $.parseHTML("<h1>This note failed to generate.</h1>"),
        };
      } else {
        payload = handedPayload;
      }
      $(".prompt-ml-container").trigger("prompt-ml:note-added", {
        payload: payload,
      });
    });
    $(newNote)
      .find(".close")
      .on("mouseup", function (e) {
        e.stopPropagation();
        var parentNote = $(this).parent().parent().parent();
        if (!$(parentNote).hasClass("wasClosed")) {
          $(this)
            .parent()
            .parent()
            .css("background-color", "#A3A3A3")
            .find(".more h2")
            .css("background-color", "#939393");
          $(".prompt-ml-container").append($(parentNote));
          $(parentNote).addClass("wasClosed");
        } else {
          $(this)
            .parent()
            .parent()
            .css("background-color", "#F0B744")
            .find(".more h2")
            .css("background-color", "#F1A204");
          $(".prompt-ml-container").prepend($(parentNote));
          $(parentNote).removeClass("wasClosed");
        }
      });
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
    var note_count: number = 0;
    console.log("_onInfo");
    for (const notice_type in info_object) {
      var list_of_notes = info_object[notice_type];
      if (notice_type == "proxy") {
        this._handleProxies(list_of_notes, note_count);
        note_count += 1;
      } else if (notice_type == "error") {
        this._makeErrorMessage(list_of_notes, note_count);
        note_count += 1;
      } else if (notice_type == "resemble") {
        console.log("making resemble msg");
        this._makeResembleMsg(list_of_notes, note_count, String(kernel_id));
      } else if (notice_type == "missing") {
        console.log("making missing data message");
        this._handleMissing(list_of_notes, note_count);
      } else if (notice_type == "model_report") {
        this._makeEqOdds(list_of_notes, note_count)
      } else {
        console.log("Note type not recognized " + notice_type);
      }
    }      
  }


  private _makeEqOdds(eqOdds: { [key: string]: any }[], note_count: number) {
    var note = new PopupNotification("modelReport", false, "Model Report Note");
    note.addHeader("Model Report Note")
    // preamble on MRN
    note.addParagraph(`<p><b>The Model Report Note</b> uses the sensitivity as marked in the Protected Column Note to determine
                       the columns that will be considered in this model report. By parsing your code, the plugin is able to find the original dataframe
                       your test dataframe was derived from and uses the sensitive columns found in that dataframe to measure
                       your model's performance across groups you may have excluded in your test features.</p>`);
    // <p style="color:green"><i>${metric_name}: ${metric}</i></p>
    note.addParagraph(`<br /><p> <span style="color:green"><i>"metric_name": "metric_value"</i></span> indicates that a metric is performing some percent better than the median for that group while
                       <span style="color:red"><b>"metric_name": "metric_value"</b></span> does the same for metrics performing some percent worse than the median for that group.</p>`)
    console.log("eqodds length ",eqOdds.length); 
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
                       The plugin calculates precision, recall, F1 Score, false positive rate (FPR) and false negative rate (FNR). More information about these metrics can be found <a href="https://towardsdatascience.com/performance-metrics-confusion-matrix-precision-recall-and-f1-score-a8fe076a2262">here</a>.</p>`);
    // Send to the Jupyterlab interface to render
    var message = note.generateFormattedOutput(global_notification_count, note_count);
    this._appendNote(message);
  }

  private _handleProxies(
    proxies: { [key: string]: any }[],
    note_count: number
  ) {
    var d: { [key: string]: { [key: string]: string[] } } = {};
    for (var x = 0; x < proxies.length; x++) {
      var p: any = proxies[x];
      if (!(p["df"] in d))
        d[p["df"]] = { proxy_col_name: [], sensitive_col_name: [], p_vals: [] };
      d[p["df"]]["proxy_col_name"].push(p["proxy_col_name"]);
      d[p["df"]]["sensitive_col_name"].push(p["sensitive_col_name"]);
      d[p["df"]]["p_vals"].push(p["p"]);
    }
    var message = this._makeProxyMsg(d, note_count);
    this._appendNote(message);
  }

  private _handleMissing(
    missing_notes: { [key: string] : any}[],
    note_count: number
  ) {
    var note = this._makeMissingMsg(missing_notes, note_count);
    var message = note.generateFormattedOutput(
      global_notification_count,
      note_count
    );
    this._appendNote(message);
  }

  // To check
  private _makeResembleMsg(
    notices: any[],
    note_count: number,
    kernel_id: string
  ) {
    var note = new ProtectedColumnNote(notices, kernel_id);
    var message = note.generateFormattedOutput(
      global_notification_count,
      note_count
    );
    this._appendNote(message);
  }

  private _makeProxyMsg(d: any, note_count: number) {
    var note = new PopupNotification("proxy", false, "Proxy Columns");
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
          };
        }
        if (df["p_vals"][idx] < 0.001) {
          tableRows[columnName].correlated.push(df["proxy_col_name"][idx]);
        } else {
          tableRows[columnName].predictive.push(df["proxy_col_name"][idx]);
        }
      });
      const tableHeader = `
        <thead>
          <tr>
            <th>Column name</th>
            <th>Highest correlated columns</th>
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
          return `
          <tbody>
              <tr>
                  <td>${columnName}</td>
                  <td>${predictiveFeatures}</td>
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


    return note.generateFormattedOutput(global_notification_count, note_count);
  }

  private _makeMissingMsg(
    notice: { [key: string]: any }[],
    note_count: number
  ) {
    var note: PopupNotification = new PopupNotification(
      "missing",
      false,
      "Missing Data"
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
        console.log("modes", modes);
        var cor_col = modes[0][0];
        
//        var percent = df["missing_columns"][col_name_index]["sens_col"][cor_col]["largest_percent"];
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
    note_count: number
  ) {
    var note = new PopupNotification("errors", false, "Errors");
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
      console.log("DEBUG1:", model_notes);
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
    var message = note.generateFormattedOutput(
      global_notification_count,
      note_count
    );
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
