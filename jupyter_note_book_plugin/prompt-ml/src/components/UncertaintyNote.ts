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
            <div class="promptMl protectedColumns">
                <h1>Uncertainty Note</h1>
                <p>Boilerplate code for the uncertainty note. It has been sent ${this._notices[0]["count"]} times.
            </div>
        `);
    var htmlElem = elem[1] as any as HTMLElement;
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
