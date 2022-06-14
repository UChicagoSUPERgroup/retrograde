import { Explorer } from "./Explorer";
import { Column } from "./Column";
import $ = require("jquery");
import { ServerConnection } from "@jupyterlab/services";
import { CodeCellClient } from "./../client";
import { BackendRequest } from "../request";

export class ProtectedData {
  ////////////////////////////////////////////////////////////
  // Properties
  // Some of these are constants, others record the state of
  // the notification.
  ////////////////////////////////////////////////////////////

  // Given by user
  explorer: Explorer;
  columns: Column[];
  df: string;
  kernelId: string;
  potentialSensitivities: string[] = [
    "none",
    "gender",
    "sex",
    "pregnancy",
    "race",
    "color",
    "nationality",
    "age",
    "religion",
    "sexual_orientation",
    "disability",
    "genetic_information",
  ];
  columnNames: string[];
  // Dynamic
  _client: CodeCellClient;

  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor(notice: any, kernelId: string) {
    this.columnNames = this._findAllColumnNames(notice);
    this.df = notice["df"];
    this.kernelId = kernelId;
    this.columns = this._populateColumns(notice);
    this._client = new CodeCellClient();
    this.explorer = new Explorer(this.columnNames, this.df);
    this.explorer.onChange((c: number, d: string) => {
      this._onExplorerChange(c, d, this);
    });
  }

  ////////////////////////////////////////////////////////////
  // Helper functions
  // Low-level functions that tend to be repeated often
  ////////////////////////////////////////////////////////////

  private _generateElement(type: string, content: string): HTMLElement {
    var elem = document.createElement(type);
    elem.innerHTML = content;
    return elem;
  }

  _onExplorerChange(columnIndex: number, dfName: string, elem: ProtectedData) {
    var columnName = this.columnNames[columnIndex];
    var explorer = $(".promptMl.protectedColumns").find(`#${dfName} .explorer`);
    explorer.find("summary").text(columnName);
    BackendRequest.userInput(
      {
        type: "user_input",
        input_type: "columnInformation",
        df: dfName,
        kernel: this.kernelId,
        col: columnName,
      },
      (raw: string) => {
        var res = JSON.parse(raw);
        explorer.find(".classification").text(res["sensitivity"]["fields"]);
        explorer.find(".value-container").html(this._columnInfoElement(res));
        explorer.find("details").prop("open", false);
      }
    );
    BackendRequest.sendTrackPoint(
      "user_input",
      `User requested information for ${columnName}`
    );
  }

  _onColumnChange(
    columnName: string,
    dfName: string,
    newSensitivity: string,
    columnIndex: number,
    elem: ProtectedData
  ): void {
    elem.columns[columnIndex] = new Column(
      columnName,
      newSensitivity != "none" ? true : false,
      newSensitivity,
      dfName,
      elem.potentialSensitivities,
      columnIndex
    );
    elem.columns[columnIndex].onChange(
      (c: string, d: string, n: string, cI: number) => {
        elem._onColumnChange(c, d, n, cI, elem);
      }
    ); // To do: add this to the constructor instead of
    // calling it immediately after making it
    var elemToChange = $(".promptMl.protectedColumns").find(
      `#${dfName} .sensitivity .dfColumn`
    )[columnIndex];
    var newColumn = elem.requestColumn(columnIndex);
    $(newColumn).insertAfter(elemToChange);
    $(elemToChange).remove();
    this._client
      .request(
        "exec",
        "POST",
        JSON.stringify({
          type: "user_input",
          input_type: "sensitivityModification",
          df: dfName,
          col: columnName,
          kernel: this.kernelId,
          sensitivity: newSensitivity,
        }),
        ServerConnection.makeSettings()
      )
      .then((res) => {
        console.log("Backend responded to the update request with:", res);
      });
    BackendRequest.sendTrackPoint(
      "user_input",
      `User updated sensitivity for col ${columnName} to ${newSensitivity}`
    );
  }

  private _populateColumns(notice: any): Column[] {
    var columns: Column[] = [];
    var dfName = notice["df"];
    var providedColumns = notice["columns"];
    var index = 0;
    for (var columnName in providedColumns) {
      var columnSensitive = providedColumns[columnName]["sensitive"],
        columnTypeOfSensitivity: string = providedColumns[columnName].field;
      if (columnTypeOfSensitivity == null) columnTypeOfSensitivity = "none";
      var column = new Column(
        columnName,
        columnSensitive,
        columnTypeOfSensitivity,
        dfName,
        this.potentialSensitivities,
        index
      );
      column.onChange((c: string, d: string, n: string, cI: number) => {
        this._onColumnChange(c, d, n, cI, this);
      });
      columns.push(column);
      index++;
    }
    return columns;
  }

  private _findAllColumnNames(notice: any): string[] {
    var colNames = [];
    for (var colName in notice["columns"]) {
      colNames.push(colName);
    }
    return colNames;
  }

  ////////////////////////////////////////////////////////////
  // Abstractions
  ////////////////////////////////////////////////////////////

  public requestColumn(columnIndex: number): HTMLDivElement {
    return this.columns[columnIndex].export();
  }

  public exportColumns(): HTMLDivElement {
    var returnElement: HTMLDivElement = this._generateElement(
      "div",
      ""
    ) as HTMLDivElement;
    for (var x = 0; x < this.columns.length; x++) {
      returnElement.appendChild(this.columns[x].export());
    }
    return returnElement;
  }

  public exportExplorer(): HTMLDivElement {
    return this.explorer.export();
  }

  _columnInfoElement(res: any) {
    var vc_str: string = "";

    for (const value in res["valueCounts"]) {
      const count = res["valueCounts"][value];
      vc_str += "<p class=values>";
      vc_str += value;
      vc_str += " : ";
      vc_str += count;
      vc_str += "</p>";
    }

    return vc_str;
  }
}
