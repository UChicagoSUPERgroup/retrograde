
import {
  JupyterFrontEnd
} from "@jupyterlab/application"

import {
  INotebookTracker,
  NotebookPanel,
} from "@jupyterlab/notebook";

import {
  Listener,
} from "./cell-listener";

import { PopupNotification } from "./components/PopupNotification";
import { ProtectedColumnNote } from "./components/ProtectedColumnNote";



import $ = require('jquery');

// Global used to construct unique ID's 
// This is increased by 1 everytime that a group of notifications is received by the frontend
// Allows us to have a unique ID for every notification so that repeat notes will open the same widget
var global_notification_count: number = 0

export class Prompter {
  // This generates prompts for notebook cells on notification of new data or a new model
  constructor(listener: Listener, tracker: INotebookTracker, app: JupyterFrontEnd, factory: NotebookPanel.IContentFactory) {
    listener.infoSignal.connect(
      (sender: Listener, output: any) => {
        this._onInfo(output)
      });
  }

  private _appendNote(note : any) {
    console.log(note);
    this._appendMsg((note[0] as HTMLDivElement).outerHTML, note[1]);
  }

  private _appendMsg(msg: string, handedPayload: any) {
    var newNote = $.parseHTML(msg)
    $(".prompt-ml-container").prepend(newNote)
    $(newNote).on("mouseup", function () {
      if (handedPayload == {}) {
        var payload: object = {
          "title": "Default Page",
          "htmlContent": $.parseHTML("<h1>This note failed to generate.</h1>"),
        }
      } else {
        payload = handedPayload
      }
      $(".prompt-ml-container").trigger("prompt-ml:note-added", { "payload": payload })
    })
    $(newNote).find(".close").on("mouseup", function (e) {
      e.stopPropagation()
      var parentNote = $(this).parent().parent().parent()
      if (!($(parentNote).hasClass("wasClosed"))) {
        $(this).parent().parent().css("background-color", "#A3A3A3").find(".more h2").css("background-color", "#939393")
        $(".prompt-ml-container").append($(parentNote))
        $(parentNote).addClass("wasClosed")
      } else {
        $(this).parent().parent().css("background-color", "#F0B744").find(".more h2").css("background-color", "#F1A204")
        $(".prompt-ml-container").prepend($(parentNote))
        $(parentNote).removeClass("wasClosed")
      }
    })
    var divs = $(".prompt-ml-container > div")
    for (var x = 0; x < divs.length; x++) {
      var targetDiv = divs[x]
      if ($(newNote).is($(targetDiv))) continue
      if ($(targetDiv).text() == $(newNote).text()) {
        $(targetDiv).remove()
      }
    }
  }

  // Main notification handling function
  private _onInfo(info_object: any) {

    var kernel_id = info_object["kernel_id"]
    var note_count: number = 0
    console.log("_onInfo");
    for (const notice_type in info_object) {
      var list_of_notes = info_object[notice_type]
      if (notice_type == "proxy") {
        this._handleProxies(list_of_notes, note_count)
        note_count += 1
      } else if (notice_type == "error") {
        this._makeErrorMessage(list_of_notes, note_count);
        note_count += 1
      } else if (notice_type == "resemble") {
        console.log("making resemble msg");
        this._makeResembleMsg(list_of_notes, note_count, String(kernel_id))
      } else if (notice_type == "missing") {
        console.log("making missing data message");
        this._handleMissing(list_of_notes, note_count);
      } else if (notice_type == "eq_odds") {
        this._makeEqOdds(list_of_notes, note_count)
      } else {
        console.log("Note type not recognized "+notice_type);
      }
    }      
  }


  private _makeEqOdds(eqOdds: { [key: string]: any }[], note_count: number) {
    var note = new PopupNotification("eqOdds", false, "Model Report Note");
    note.addHeader("Model Report Note")
    for(var x = 0; x < eqOdds.length; x++) {
      var model : { [key: string] : any} = eqOdds[x];
      // Name and accuracy to the first decimal place (i.e. 10.3%)
      note.addSubheader("Model " + model["model_name"] + " (" + (Math.floor(1000 * model["acc_orig"]) / 10) + "% accuracy)")
      var sensitivityLists : any[] = []
      // Iterates over error rates and creates nested arrays for a bulleted list
      // i.e.
      // [
      //    <parent group name>: [
      //        <nested group name> : [
      //          "Precision: <precision score>",
      //          "Recall: <recall score"
      //        ],
      //        <second nested group name : [...],
      //    ],
      //    <second parent group name: [...],
      //    ...
      // ]
      for(var group in model["error_rates"]) {
        sensitivityLists.push(group)
        for(var correspondingGroup in model["error_rates"][group]) {
          var thisGroup = model["error_rates"][group][correspondingGroup]
          // Round to 3 decimal places
          // To do: dedicated rounding method / global rounding config setting
          for(var x = 0; x < thisGroup.length; x++)
            thisGroup[x] = Math.floor(model["error_rates"][group][correspondingGroup][x] * 1000) / 1000
          // Backend sends information in a static, predefined order
          var precision = thisGroup[0],
          recall = thisGroup[1],
          f1score = thisGroup[2],
          fpr = thisGroup[3],
          fnr = thisGroup[4]
          var nextAppend : any[] = [correspondingGroup, [
            "Precision: " + precision, 
            "Recall: " + recall, 
            "F1 Score: " + f1score, 
            "FPR: " + fpr, 
            "FNR: " + fnr
          ]] 
          sensitivityLists.push(nextAppend)
        }
      }
      // Attaching the data to the note itself
      note.addParagraph("Sensitive groups:")
      note.addList((sensitivityLists.length == 0) ? ["None"] : sensitivityLists)
    }
    // Send to the Jupyterlab interface to render
    var message = note.generateFormattedOutput(global_notification_count, note_count);
    this._appendNote(message);
  }

  private _handleProxies(proxies: { [key: string]: any }[], note_count: number) {
    var d: { [key: string]: { [key: string]: string[] } } = {};
    for (var x = 0; x < proxies.length; x++) {
      var p: any = proxies[x];
      if (!(p["df"] in d)) d[p["df"]] = { "proxy_col_name": [], "sensitive_col_name": [], "p_vals": [] };
      d[p["df"]]["proxy_col_name"].push(p["proxy_col_name"]);
      d[p["df"]]["sensitive_col_name"].push(p["sensitive_col_name"]);
      d[p["df"]]["p_vals"].push(p["p"]);
    }
    var message = this._makeProxyMsg(d, note_count);
    this._appendNote(message);
  }

  private _handleMissing(missing_notes: { [key: string]: { [key: string]: any } }, note_count: number){
    var note = this._makeMissingMsg(missing_notes, note_count)
    var message = note.generateFormattedOutput(global_notification_count, note_count);
    this._appendNote(message);
  }

  // To check
  private _makeResembleMsg(notices : any[], note_count : number, kernel_id : string) {
    var note = new ProtectedColumnNote(notices, kernel_id);
    var message = note.generateFormattedOutput(global_notification_count, note_count);
    this._appendNote(message);
  }


  private _makeProxyMsg(d: any, note_count: number) {
    var note = new PopupNotification("proxy", false, "Proxy Columns");
    note.addHeader("Proxy Columns Note");
    note.addList([
      "Certain variables in this notebook may encode or have strong correlations with sensitive variables. In some cases, the use of these correlated variables may produce outcomes that are biased. This bias may be undesirable, unethical and in some cases illegal. <a style=\"color: blue; text-decoration; underline\" target=\"_blank\" href=\"PLACEHOLDER\">(Read More)</a>",
      "This plugin has detected the presence of certain columns in this notebook that may be correlated with sensitive variables. In some instances, this correlation was detected by computing the correlation between the sensitive column and the candidate proxy column.",
      [
        "A column may also be correlated with a sensitive variable that is not contained in the data. This plugin also notes when a column may encode data that is known to correlate with a sensitive variable that is not present in the dataset."
      ],
      "The correlations found or suggested here may or may not be meaningful. There also may be situation-specific correlations that are not detected by this plugin."
    ])
    for (let df_name in d) {
      note.addHeader(`Within <strong>${df_name}</strong>`);
      var df = d[df_name];
      let ul: string[] = [];
      for (var x = 0; x < df["proxy_col_name"].length; x++) {
        ul.push(`Column <strong>${df["proxy_col_name"][x]}</strong> ${(df["p_vals"][x] < 0.001) ? "is strongly correlated with" : "may be predictive of"} <strong>${df["sensitive_col_name"][x]}</strong>.`) // Rounds to the third decimal place
      };
      note.addList(ul);
    }
    return note.generateFormattedOutput(global_notification_count, note_count);
  }

  private _makeMissingMsg(notice: { [key: string]: { [key: string]: any } }, note_count: number) {
    var note : PopupNotification = new PopupNotification("missing", false, "Missing Data")
    note.addHeader("Missing Data Note")
    note.addParagraph(`here are a number of reasons why data may be missing. In some instances, 
    it may be due to biased collection practices. It may also be missing due to random 
    error <a href=\"placeholder\"(Read More)</a>`);
    note.addParagraph(`This plugin cannot detect whether the missing data are missing at random or whether 
    they are missing due to observed or unobserved variables.`);
    // Create container for the small-view content
    // Iterating over every dataframe
    for (var df_name in notice["dfs"]) {
      // Small-view df container
      note.addSubheader(`<h3>Within ${df_name}</h3>`);
      var df = notice["dfs"][df_name]
      var ul = []
      // Expanded-view df container
      // Iterating over every column
      for (const col_name_index in df["missing_columns"]) {
        // Extract information for the small-view content
        var col_name = df["missing_columns"][col_name_index]
        var col_count = df[col_name]["number_missing"]
        var total_length = df[col_name]["total_length"]
        // Extract the mode (for expanded view)
        var modes = []
        for (const key in df[col_name]) {
          if (key == "total_length" || key == "number_missing") continue
          else modes.push([key, df[col_name][key]["largest_percent"]])
        }
        modes = modes.sort((a: [string, number][][], b: [string, number][][]) => {
          if (a[1] === b[1]) {
            return 0;
          }
          else {
            return (a[1] > b[1]) ? -1 : 1;
          }
        })
        var cor_col = modes[0][0]
        var percent = df[col_name][cor_col]["largest_percent"]
        var cor_mode = df[col_name][cor_col]["largest_missing_value"]
        ul.push(`Column <strong>${col_name}</strong> is missing <strong>${col_count}</strong>/<strong>${total_length}</strong> entries`)
        ul.push([`This occurs most frequently (${percent}%) when ${cor_col} is ${cor_mode}`])
      }
      note.addList(ul);
    }
    return note
  }

  private _makeErrorMessage(notices: { [key: string]: any }[], note_count: number) {
    var note = new PopupNotification("errors", false, "Errors Note");
    note.addHeader("Errors Note");
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
      var notice = notices[x]
      if (!(notice["model_name"] in models)) models[notice["model_name"]] = {
        "fpr": [],
        "fnr": []
      };
      models[notice["model_name"]][notice["metric_name"]].push({
        "slice": notice["slice"],
        "count": notice["n"],
        "metric_in": notice["metric_in"],
        "metric_out": notice["metric_out"],
        "pos_value": notice["pos_value"],
        "neg_value": notice["neg_value"],
      });
    }
    // Generating the dynamic content
    for (var model_name in models) {
      var model_notes = models[model_name];
      if (model_notes["fpr"].length == 0 || model_notes["fnr"].length == 0)
        continue
      console.log("DEBUG1:", model_notes)
      var fprString = this._makeErrorNoteLists(model_notes["fpr"], `Assuming ${model_notes["fpr"][0]["pos_value"]} given the true value of ${model_notes["fpr"][0]["neg_value"]}`);
      var fnrString = this._makeErrorNoteLists(model_notes["fnr"], `Assuming ${model_notes["fnr"][0]["neg_value"]} given the true value of ${model_notes["fnr"][0]["neg_value"]}`);
      note.addList([
        `In the model ${model_name}, there was an unusually high probability of:`,
        [
          fprString,
          fnrString
        ]
      ])
    }
    // Adding static content; creating response object
    var message = note.generateFormattedOutput(global_notification_count, note_count);
    this._appendNote(message);
  }

  // Takes in a list of slice objects with metric / positive value / negative value information
  private _makeErrorNoteLists(segments: { [key: string]: any }[], metricName: string) {
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
      returnArray[1].push(sliceString)
      returnArray[1].push([`Slice size was ${segments[x]["count"]}. The outside metric is ${Math.floor(segments[x]["metric_out"] * 100) / 100}. The inside metric is ${Math.floor(100 * segments[x]["metric_in"]) / 100}.`]);
    }
    return returnArray;
  }

}
