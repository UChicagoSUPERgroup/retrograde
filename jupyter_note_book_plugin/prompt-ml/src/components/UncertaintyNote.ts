import { PopupNotification } from "./PopupNotification";
// import * as $ from "jquery"; // jQuery for local testing
import $ = require("jquery"); // jQuery for plugin

export class UncertaintyNote extends PopupNotification {
  ////////////////////////////////////////////////////////////
  // Properties
  // Some of these are constants, others record the state of
  // the notification.
  ////////////////////////////////////////////////////////////

  private _notices: { [key: string]: any }[];

  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor(notices: any[]) {
    super("uncertainty", false, "Uncertainty Note", notices);
    this._notices = notices;
    super.addRawHtmlElement(this._generateBaseNote());
  }

  ////////////////////////////////////////////////////////////
  // Helper functions
  // Low-level functions that tend to be repeated often
  ////////////////////////////////////////////////////////////

  private _generateBaseNote(): HTMLElement {
    var elem = $.parseHTML(`
            <div class="promptMl uncertaintyNote">
                <h1>Uncertainty Note</h1>
                <div class="models">
                </div>
            </div>
    `);
    for (var model of this._notices) {
      $(elem).find(".models").append(this._generateModelContent(model));
    }
    return elem[1] as any as HTMLElement;
  }

  private _generateModelContent(model: { [key: string]: any }): HTMLElement {
    var elem = $.parseHTML(`
      <div class="noselect model shadowDefault" prompt-ml-tracking-enabled prompt-ml-tracker-interaction-description="Toggled model tab (${model["model_name"]})">
        <h2><span class="prefix"> - </span>Within <span class="code-snippet">${model["model_name"]}</span></h2>
        <div class="toggleable"></div>
      </div>
    `);
    // handle expanded / condensed views
    $(elem)
      .find("h2")
      .on("mouseup", (e: Event) => {
        var parentElem = $($(e.currentTarget).parent());
        // Toggle basic visibility effects
        parentElem.toggleClass("condensed");
        // Change prefix to "+" or "-" depending on if the note is condensed
        parentElem
          .find("h2 .prefix")
          .text(parentElem.hasClass("condensed") ? " + " : " - ");
      });
    // generate summary
    $(elem).find(".toggleable").append(this._generateSummary(model));
    // generate table
    $(elem).find(".toggleable").append(this._generateTable(model));
    // prepare selector interactivity
    const onPress = (columnName: string) => {
      $(elem).find(`tr[modified="original"]`).removeAttr("modified");
      $(elem).find("table .active").removeClass("active");
      $(elem).find("table th").removeClass("active");
      $(elem).find(`*[id*="${columnName}"]`).addClass("active");
      $(elem).find(`table *[modified*="${columnName}"]`).addClass("active");
      if (columnName.indexOf(",") >= 0) {
        var columnsString = this._splitArrayOfColumns(columnName);
        var columns = columnsString.split(", ");
        for (var column of columns) {
          $(elem).find(`table *[id*="${column}"]`).addClass("active");
        }
      }
    };
    // generate interactivity
    $(elem).find(".toggleable").prepend(this._generateSelector(model, onPress));

    return elem[1] as HTMLElement;
  }

  private _extractRows(model: {
    [key: string]: any;
  }): { [key: string]: any }[] {
    var modified_values: { [key: string]: any } = model.modified_values;
    var original_results: boolean[] = model.original_results;
    var rows = model.original_values.map((e: number[], i: number) => {
      var row = { original: [...e, original_results[i] ? 1 : 0] };
      for (var [modifiedColumnName, values] of Object.entries(
        modified_values
      )) {
        var rowValues: number[][] = values["0"];
        row = Object.assign({}, row, {
          [modifiedColumnName]: [
            ...rowValues[i],
            model.modified_results[modifiedColumnName][0][i] ? 1 : 0,
          ],
        });
      }
      return row;
    });
    return rows;
  }

  private _generateSelector(
    model: { [key: string]: any },
    onSelect: Function
  ): HTMLElement {
    const dropdownSvg = `<svg class="dropdown-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500"><path class="dropdown-path" d="M325.607,79.393c-5.857-5.857-15.355-5.858-21.213,0.001l-139.39,139.393L25.607,79.393 c-5.857-5.857-15.355-5.858-21.213,0.001c-5.858,5.858-5.858,15.355,0,21.213l150.004,150c2.813,2.813,6.628,4.393,10.606,4.393 s7.794-1.581,10.606-4.394l149.996-150C331.465,94.749,331.465,85.251,325.607,79.393z" /></svg>`;
    var elem = $.parseHTML(
      `<div class="dropdown"><div class="selected"><p>Select columns to modify</p>${dropdownSvg}</div><div class="options"></div></div>`
    );
    for (var columnName of Object.keys(model.modified_values))
      $(elem)
        .find(".options")
        .append($.parseHTML(`<p id="${columnName}">${columnName}</p>`));
    $(elem).on("mouseup", (e: Event) => {
      if ($(e.target).prop("id")) {
        $(elem).find(".selected p").text($(e.target).prop("id"));
        onSelect($(e.target).prop("id"));
      }
      $(elem).toggleClass("active");
    });
    return elem[0] as any as HTMLElement;
  }

  private _generateSummary(model: { [key: string]: any }): HTMLElement {
    var elem = $.parseHTML(
      `<div class="summary"><h4>Modifications Summary</h4><ul class="modificationSummaries"></ul></div>`
    );
    const statistics: { [key: string]: any } = model["ctf_statistics"];
    for (var [colName, colStats] of Object.entries(statistics)) {
      if (colName == "biggest_diff") continue; // special case
      colName = this._splitArrayOfColumns(colName);
      var colSummary = $.parseHTML(
        `<li>When we modified <strong>${colName}</strong>:</li><ul></ul>`
      );
      $(colSummary[1]).append(
        $.parseHTML(
          `<li><strong>${this._r(
            colStats["accuracy"][0] * 100,
            3
          )}</strong>% of predictions were accurate</li>`
        )
      );
      $(colSummary[1]).append(
        $.parseHTML(
          `<li><strong>${colStats["raw_diff"]}</strong> predictions changed</li><ul class="predictionsSublist"></ul>`
        )
      );
      $(colSummary[1])
        .find(".predictionsSublist")
        .append(
          $.parseHTML(
            `<li><strong>${colStats["true_to_False"]}</strong> changed from <strong>true</strong> to <strong>false</strong></li>
            <li><strong>${colStats["false_to_True"]}</strong> changed from <strong>true</strong> to <strong>false</strong></li>`
          )
        );
      $(elem).find("ul.modificationSummaries").append(colSummary);
    }
    return elem[0] as any as HTMLElement;
  }

  private _generateTable(model: { [key: string]: any }): HTMLElement {
    // get rows in an easaier format
    var rows = this._extractRows(model);
    var elem = $.parseHTML("<table></table>");
    // generate column titles
    var headers = $.parseHTML("<tr></tr>");
    for (var columnName of model["columns"])
      $(headers).append(this._generateCell(columnName, true));
    // static columns
    $(headers).append(this._generateCell("prediction", true));
    $(elem).append(headers);
    // Generate rows
    for (var row of rows) {
      var numModifications = Object.keys(row).length;
      var tableRows = Array.from(Object.keys(row), (name, i) =>
        $.parseHTML(`<tr modified="${name}"></tr>`)
      );
      for (var x = 0; x < row.original.length; x++) {
        for (var y = 0; y < numModifications; y++) {
          var originalValue = row.original[x];
          var newValue = row[Object.keys(row)[y]][x];
          if (originalValue == newValue)
            $(tableRows[y]).append(
              this._generateCell(this._r(originalValue, 3))
            );
          else
            $(tableRows[y]).append(
              this._generateCell(
                `<span class="new">${this._r(
                  newValue,
                  3
                )}</span> <span class="old">${this._r(
                  originalValue,
                  3
                )}</span>`,
                false,
                true
              )
            );
        }
      }
      for (var tableRow of tableRows) $(elem).append(tableRow);
    }

    return elem[0] as HTMLElement;
  }

  private _roundNumber(num: number, to: number) {
    return (
      Math.round((num + Number.EPSILON) * Math.pow(10, to)) / Math.pow(10, to)
    );
  }

  private _r(num: number, to: number): string {
    return this._roundNumber(num, to) + "";
  }

  private _generateCell(
    content: string,
    header = false,
    modified = false
  ): HTMLElement {
    return $.parseHTML(
      `<t${header ? "h" : "d"} ${header ? `id="${content}"` : ""} ${
        modified ? 'class="modified"' : ""
      }>${content}</t${header ? "h" : "d"}>`
    )[0] as HTMLElement;
  }

  private _splitArrayOfColumns(columnString: string): string {
    return columnString
      .replace(/ /g, "")
      .replace(/'/g, "")
      .replace("(", "")
      .replace(")", "")
      .replace(/,/g, ", ");
  }

  ////////////////////////////////////////////////////////////
  // Abstractions
  // Tries to make note generation more intuitive and consistent across
  // different note types and styles.
  ////////////////////////////////////////////////////////////

  public _populateNote(): HTMLDivElement {
    var elem = document.createElement("div");
    elem.classList.add("promptMl");
    elem.style.cssText = "padding: 15px; overflow: scroll;";
    return elem;
  }

  export(): HTMLDivElement {
    return this._content; // doesn't clone, returns the actual element -- prevents the event listeners from being removed
  }
}
