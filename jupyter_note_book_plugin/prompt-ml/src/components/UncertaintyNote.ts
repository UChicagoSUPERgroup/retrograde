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
    super("uncertainty", false, "Counterfactuals", notices);
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
                <h1>Counterfactual Notification</h1>
                <p>
                A counterfactual is a conditional statement used to reason about what could 
                have been true under different circumstances. "If Brenda were allergic to apples 
                she would not eat an apple every day" is an example of a counterfactual 
                statement. In the machine learning setting, a counterfactual means perturbing 
                each data point and observing how this impacts the predictions made by a model.
                </p>
                <br />
                <p>
                <b>How does Retrograde do this?</b> <br />
                For numerical features, Retrograde randomly adds or subtracts less than half a 
                standard deviation (the standard deviation of your test data set) from each row instance.
                For one-hot encoded features or categorical features, Retrograde randomly 
                chooses a value different than the current row's value.
                </p>
                <br />
                <p>
                <b>Why should I be concerned?</b> <br />
                When you are building a machine learning model, it is sometimes difficult to 
                know how a model will perform on out-of-distribution data (i.e., data instances 
                it has not previously seen). Consequently, it may be difficult to solely use 
                the accuracy of a model as a measure. This uncertainty is a result of the 
                inability to know the degree to which your model has "generalized" and 
                "learned" from the data. 
                </p>
                <br />
                <b>What can I do about it?</b> <br />  
                Retrograde provides brief statistics about the number of predictions affected by 
                the perturbations as well as how the predictions were affected (i.e., 
                quantifying the changes from True to False or False to True). Use the dropdown 
                menu to select which modified column or combination of columns to view in the 
                table. Once a selection is made, the table below the summary will show the
                original data side-by-side with the modified column(s) in orange.
                It is up to you to interpret and evaluate the ramifications of the counterfactual 
                predictions presented to determine if there exist systemic issues or outliers with 
                the results of the counterfactual predictions.               
                </p>
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
      <div class="noselect model shadowDefault" prompt-ml-tracking-enabled prompt-ml-tracker-interaction-description="Toggled model tab (${
        model["model_name"]
      })">
        <h2><span class="prefix"> - </span>Within <span class="code-snippet">${
          model["model_name"]
        }</span> Original Accuracy: ${UncertaintyNote._r(
      model["original_accuracy"] * 100,
      1
    )}%</h2>
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
    $(elem).find(".toggleable").append(this._generateSummary(model));
    // generate table
    $(elem)
      .find(".toggleable")
      .append($.parseHTML(`<div class="tableContainer"></div>`));
    $(elem)
      .find(".toggleable .tableContainer")
      .append(this._generateTable(model));
    // generate summary
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
    $(elem)
      .find(".toggleable .tableContainer")
      .prepend(this._generateSelector(model, onPress));
    // generate title
    const tableHeader = document.createElement("h4");
    tableHeader.innerText = "Modifications Table";
    $(elem).find(".toggleable .tableContainer").prepend(tableHeader);
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
    for (var columnName of Object.keys(model.modified_values)
      .sort()
      .filter((columnName) => model.ctf_statistics[columnName].raw_diff > 0)) {
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
      if (colStats["raw_diff"] == 0) continue;
      colName = this._splitArrayOfColumns(model, colName);
      var colSummary = $.parseHTML(
        `<li>When we modified <strong>${colName}</strong>:</li><ul></ul>`
      );
      $(colSummary[1]).append(
        $.parseHTML(
          `<li><strong>${UncertaintyNote._r(
            colStats["accuracy"][0] * 100,
            1
          )}%</strong> of predictions were accurate <strong>(${UncertaintyNote._r(
            model["original_accuracy"] * 100,
            1
          )}% in original model)</strong></li>`
        )
      );
      $(colSummary[1]).append(
        $.parseHTML(
          `<li><strong>${colStats["raw_diff"]} (${UncertaintyNote._r(
            (colStats["raw_diff"] / colStats["total"]) * 100,
            1
          )}%)</strong> predictions changed</li>
          <ul class="predictionsSublist"></ul>`
        )
      );
      $(colSummary[1])
        .find(".predictionsSublist")
        .append(
          $.parseHTML(
            `<li><strong>${colStats["true_to_False"]} (${UncertaintyNote._r(
              (colStats["true_to_False"] / colStats["total"]) * 100,
              1
            )}%)</strong> changed from <strong>True</strong> to <strong>False</strong></li>
            <li><strong>${colStats["false_to_True"]} (${UncertaintyNote._r(
              (colStats["false_to_True"] / colStats["total"]) * 100,
              1
            )}%)</strong> changed from <strong>False</strong> to <strong>True</strong></li>`
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
          x == 0
            ? "index"
            : "" + model.ctf_statistics[selectedGroupLabel].diff_indices[index],
          x == 0,
          null
        )
      );
      // prediction
      row.prepend(
        UncertaintyNote._generateCell(
          x == 0
            ? "prediction"
            : model.modified_results[selectedGroupLabel][index][0],
          x == 0,
          x == 0
            ? null
            : "" + model.modified_results[selectedGroupLabel][index][1],
          true
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
          x != 0 &&
            modifiedIndices.indexOf(y - 1) >= 0 &&
            rowData[y - 1] != rowData[y]
            ? UncertaintyNote._r(rowData[y - 1], 3)
            : null,
          x == 0 && modifiedIndices.indexOf(y - 1) >= 0
        );
        row.appendChild(cell);
      });
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
            ? // ? `<span class="new">${content}</span><span class="old">${modified}</span>`
              `<span class="old">${modified}</span>➜<span class="new">${content}</span>`
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
