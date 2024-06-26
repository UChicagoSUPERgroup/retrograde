import { PopupNotification } from "./PopupNotification";
import { ProtectedData } from "./ProtectedData";
import $ = require("jquery");

export class ProtectedColumnNote extends PopupNotification {
  ////////////////////////////////////////////////////////////
  // Properties
  // Some of these are constants, others record the state of
  // the notification.
  ////////////////////////////////////////////////////////////

  private _data: ProtectedData[];
  private _dfs: string[];
  private _notices: { [key: string]: any };

  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor(
    notices: any[],
    kernel_id: string,
    originalMessage: { string: any }[]
  ) {
    super("protected", true, "Protected Columns", originalMessage);
    this._data = [];
    this._dfs = [];
    this._notices = originalMessage;
    notices.reverse();
    this._notices.sort(
      (dfA: { [key: string]: any }, dfB: { [key: string]: any }) =>
        this._countNoticeSensitivityLength(dfB) -
        this._countNoticeSensitivityLength(dfA)
    );
    for (var x = 0; x < notices.length; x++) {
      this._data.push(new ProtectedData(notices[x], kernel_id));
      this._dfs.push(notices[x]["df"]);
      this._notices[notices[x]["df"]] = notices[x];
    }
    super.addRawHtmlElement(this._generateBaseNote(this._dfs));
  }

  ////////////////////////////////////////////////////////////
  // Helper functions
  // Low-level functions that tend to be repeated often
  ////////////////////////////////////////////////////////////

  private _countNoticeSensitivityLength(df: {
    [key: string]: { [key: string]: any };
  }): number {
    return Object.entries(df.columns).reduce(
      (sum, [key, entry]) => (sum += entry.sensitive ? 1 : 0),
      0
    );
  }

  private _generateBaseNote(dfs: any[]): HTMLElement {
    var dfString = "";
    console.log(dfs);
    for (var x = 0; x < dfs.length; x++) {
      dfString += `<div class="dfs">
            <div class="noselect df shadowDefault" id=${dfs[x]} prompt-ml-tracking-enabled prompt-ml-tracker-interaction-description="Toggled dataframe tab (${dfs[x]})">
                <h1><span class="prefix"> - </span>Within <span class="code-snippet">${dfs[x]}</span></h1>
                <div class="sensitivity">
                    <h2>Column Sensitivity</h2>
                    <p class="columnSensitivityExplanation">Below you can assign each of the columns
                    in ${dfs[x]} to one of the standard protected classes. Then you'll have the opportunity
                    to explore some facts about this class.</p>
                    <!-- Dropdown from https://codepen.io/havardob/pen/KKqYGYj -->
                    <!-- All columns go here, append to "sensitivity" -->
                </div>
                <div class="column explorer shadowDefault" prompt-ml-tracking-enabled prompt-ml-tracker-interaction-description="Explorer interaction (${dfs[x]})">
                </div>
            </div>
        </div>`;
    }
    const joinedColumnNames = dfs
      .filter(
        (dfName) =>
          this._countNoticeSensitivityLength(this._notices[dfName]) >= 1
      )
      .join(", ");
    var elem = $.parseHTML(`
            <div class="promptMl protectedColumns">
                <h1>Protected Columns</h1>
                <div class="intro">
                    <p>Some of the columns in the <strong>${joinedColumnNames}</strong> dataframe feature protected classes of data. 
                    A protected class is group of people sharing a common trait who are legally 
                    protected from being discriminated against on the basis of that trait. 
                    Some examples include race, gender, and pregnancy status.
                    <br /><br /><strong>Why should I be concerned?</strong>
                    <br />When you are building machine learning models off of data that includes 
                    information from protected classes, you may be inadvertently replicating power
                    structures that cause violence and harm, which could play into how your model makes predictions.
                    <br /><br /><strong>What can I do about it?</strong>
                    <br />Below, the column sensitivity picker will allow you to decide if a column represents one of the protected groups (note this is not necessarily the same as being correlated to a protected group). 
                    Retrograde uses that sensitivity decision in other notifications to show you more information about your data and/or model.</p>
                </div>
                ${dfString}
            </div>
        `);
    var htmlElem = elem[1] as any as HTMLElement;
    // attach method to expand / contract the content to each individual df h1
    var listOfDataframeHeaders: NodeListOf<Element> =
      htmlElem.querySelectorAll(".df h1");
    for (var dataframeHeader of listOfDataframeHeaders) {
      (dataframeHeader as HTMLElement).onmouseup = (e: Event) => {
        var parentElem = $($(e.currentTarget).parent());
        // Toggle basic visibility effects
        parentElem.toggleClass("condensed");
        // Change prefix to "+" or "-" depending on if the note is condensed
        parentElem
          .find("h1 .prefix")
          .text(parentElem.hasClass("condensed") ? " + " : " - ");
      };
    }
    for (var x = 0; x < this._data.length; x++) {
      htmlElem
        .querySelector(`#${this._data[x]["df"]} .sensitivity`)
        .appendChild(this._data[x].exportColumns());
      htmlElem
        .querySelector(`#${this._data[x]["df"]} .explorer`)
        .appendChild(this._data[x].exportExplorer());
    }
    return htmlElem;
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
