import { PopupNotification } from "./PopupNotification";
import $ = require("jquery"); // jQuery for plugin

export class UncertaintyNote extends PopupNotification {
  ////////////////////////////////////////////////////////////
  // Properties
  // Some of these are constants, others record the state of
  // the notification.
  ////////////////////////////////////////////////////////////

  private _notices: { [key: string]: any }[];
  private _selectedIndex: number;

  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor(notices: any[]) {
    super("uncertainty", false, "Uncertainty Note", notices);
    this._selectedIndex = 0;
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
    for (var [colName, _] of Object.entries(model.columns)) {
      model.columns[colName].sort();
    }
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
    // generate table
    $(elem)
      .find(".toggleable")
      .append($.parseHTML(`<div class="tableContainer" />`));
    $(elem)
      .find(".toggleable .tableContainer")
      .append(this._generateTable(model));
    // generate summary
    $(elem).find(".toggleable").append(this._generateSummary(model));
    // prepare selector interactivity
    const onPress = (d: string) => {
      const keys = Object.keys(model.modified_values).sort();
      this._selectedIndex = keys.indexOf(d);
      $(elem).find("table").remove();
      $(elem)
        .find(".toggleable .tableContainer")
        .append(this._generateTable(model));
    };
    // generate interactivity
    $(elem).find(".toggleable").prepend(this._generateSelector(model, onPress));
    return elem[1] as HTMLElement;
  }

  private _generateSelector(
    model: { [key: string]: any },
    onSelect: Function
  ): HTMLElement {
    const dropdownSvg = `<svg class="dropdown-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500"><path class="dropdown-path" d="M325.607,79.393c-5.857-5.857-15.355-5.858-21.213,0.001l-139.39,139.393L25.607,79.393 c-5.857-5.857-15.355-5.858-21.213,0.001c-5.858,5.858-5.858,15.355,0,21.213l150.004,150c2.813,2.813,6.628,4.393,10.606,4.393 s7.794-1.581,10.606-4.394l149.996-150C331.465,94.749,331.465,85.251,325.607,79.393z" /></svg>`;
    var elem = $.parseHTML(
      `<div class="dropdown"><div class="selected"><p>Select columns to modify</p>${dropdownSvg}</div><div class="options"></div></div>`
    );
    for (var columnName of Object.keys(model.modified_values).sort()) {
      const displayName = model.ctf_statistics[columnName].info
        .flat()
        .join(", ");
      $(elem)
        .find(".options")
        .append(
          $.parseHTML(
            `<p id="${columnName}" displayname="${displayName}">${displayName}</p>`
          )
        );
    }
    $(elem).on("mouseup", (e: Event) => {
      if ($(e.target).prop("id")) {
        $(elem).find(".selected p").text($(e.target).attr("displayname"));
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
      colName = this._splitArrayOfColumns(model, colName);
      var colSummary = $.parseHTML(
        `<li>When we modified <strong>${colName}</strong>:</li><ul></ul>`
      );
      $(colSummary[1]).append(
        $.parseHTML(
          `<li><strong>${UncertaintyNote._r(
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
    // can change as needed with piloting
    const MAX_ROW_COUNT = 25;
    // select data to load
    const selectedGroupLabel = Object.keys(model.modified_values).sort()[
      this._selectedIndex
    ];
    let modifiedData = [
      model.columns[selectedGroupLabel],
      ...model.modified_values[selectedGroupLabel],
    ];
    if (modifiedData.length >= MAX_ROW_COUNT)
      modifiedData = modifiedData.slice(0, MAX_ROW_COUNT);
    // find column indices for modified data
    const modifiedCols = [].concat(
      ...model.ctf_statistics[selectedGroupLabel].info
    );
    const modifiedIndices = modifiedCols.map((col) =>
      model.columns[selectedGroupLabel].sort().indexOf(col)
    );
    // create dom element
    var table = document.createElement("table");
    var tableBody = document.createElement("tbody");
    modifiedData.forEach(function (rowData: any[], x: number) {
      const index = x - 1;
      var row = document.createElement("tr");
      // index
      row.appendChild(
        UncertaintyNote._generateCell(
          x == 0 ? "index" : "" + index,
          x == 0,
          null
        )
      );
      // df col data
      rowData.forEach(function (cellData, y) {
        if (modifiedIndices.indexOf(y) >= 0) return;
        var cell = UncertaintyNote._generateCell(
          x == 0
            ? modifiedIndices.indexOf(y - 1) >= 0
              ? rowData[y - 1]
              : cellData
            : UncertaintyNote._r(cellData, 3),
          x == 0,
          modifiedIndices.indexOf(y - 1) >= 0 && x != 0
            ? UncertaintyNote._r(rowData[y - 1], 3)
            : null,
          x == 0 && modifiedIndices.indexOf(y - 1) >= 0
        );
        row.appendChild(cell);
      });
      // prediction
      row.appendChild(
        UncertaintyNote._generateCell(
          x == 0
            ? "prediction"
            : model.modified_results[selectedGroupLabel][index],
          x == 0,
          model.ctf_statistics[selectedGroupLabel].diff_indices.indexOf(
            index
          ) >= 0
            ? "" + !model.modified_results[selectedGroupLabel][index]
            : null
        )
      );
      tableBody.appendChild(row);
    });
    table.appendChild(tableBody);
    return table as HTMLElement;
  }

  public static _roundNumber(num: number, to: number) {
    return (
      Math.round((num + Number.EPSILON) * Math.pow(10, to)) / Math.pow(10, to)
    );
  }

  public static _r(num: number, to: number): string {
    return this._roundNumber(num, to) + "";
  }

  public static _generateCell(
    content: string,
    header = false,
    modified: string = null,
    overrideModifiedStyling = false
  ): HTMLElement {
    return $.parseHTML(
      `<t${header ? "h" : "d"}
      ${header ? `id="${content}"` : ""}
      ${modified || overrideModifiedStyling ? "class='modified'" : ""} >
        ${
          modified
            ? `<span class="new">${content}</span><span class="old">${modified}</span>`
            : content
        }

      </t${header ? "h" : "d"}>`
    )[0] as HTMLElement;
  }

  private _splitArrayOfColumns(
    model: { [key: string]: any },
    columnString: string
  ): string {
    return model.ctf_statistics[columnString].info.flat().join(", ");
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
