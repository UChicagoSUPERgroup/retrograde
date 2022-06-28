import { PopupNotification } from "./PopupNotification";
import $ = require("jquery");

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
    console.log("uncertainty notices:", notices);
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
                <div class="model">
                  <h3>Model <span="code-snippet">lr</span></h3>
                  <div class="uncertaintyNoteTableContainer"><span style="width: 100%; display: flex; flex-direction: row; padding-bottom: 8px"><span class="labelContainer"><h4>Original</h4></span><span class="labelContainer"><h4>Race + Income</h4></span></span></div>
                  <div class="conclusions">
                    <h4>Conclusions</h4>
                    <ul>
                      <li>5 predictions changed when we modified 'race' and 'income'</li>
                      <li>2 of these changes were from True to False</li>
                      <li>3 of these changes were from False to True</li>
                      <li>The combination of <span className="code-snippet-inline">black</span> and <span className="code-snippet-inline">$80,000</span> resulted in the most changed predictions with 2 changes occuring.</li>
                    </ul>
                  </div>
                </div>
            </div>
    `);
    $(elem).find(".uncertaintyNoteTableContainer").append(this._renderTable());
    $(elem).find(".uncertaintyNoteTableContainer").append(this._renderTable("modified_values", "modified_results"));
    var htmlElem = elem[1] as any as HTMLElement;
    $(elem).find('.uncertaintyNoteTableContainer div:first-of-type').on('scroll', function (e) {
      var scrollLeft = $('.uncertaintyNoteTableContainer div:first-of-type').scrollLeft();
      $('.uncertaintyNoteTableContainer div:nth-of-type(2)').scrollLeft(scrollLeft);
    })
    $(elem).find('.uncertaintyNoteTableContainer div:nth-of-type(2)').on('scroll', function (e) {
      var scrollLeft = $('.uncertaintyNoteTableContainer div:nth-of-type(2)').scrollLeft();
      $('.uncertaintyNoteTableContainer div:first-of-type').scrollLeft(scrollLeft);
    })
    return htmlElem;
  }

  private _renderTable(values_key : string = "original_values", results_key : string = "original_results"): HTMLElement {
    var tables = this._generateElement("div", "");
    for(var notice of this._notices) {
      var table = this._generateElement("table", "");
      var headers = this._generateElement("tr", "");
      for(var columnName of notice["columns"])
        headers.appendChild(this._generateElement("th", columnName))
      headers.appendChild(this._generateElement("th", "Prediction"))
      table.appendChild(headers)
      for(var x = 0; x < notice[values_key].length; x++) {
        var data = this._generateElement("tr", "");
        for(var y = 0; y < notice[values_key][x].length; y++) {
          data.appendChild(this._generateElement("td", notice[values_key][x][y]))
        }
        data.appendChild(this._generateElement("td", "" + notice[results_key][x]))
        table.appendChild(data);
      }
      if(values_key != "original_values")
        table.classList.add("modified")
      tables.appendChild(table);
    }
    return tables;
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
