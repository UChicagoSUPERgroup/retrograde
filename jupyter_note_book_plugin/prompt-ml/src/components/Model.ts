import $ = require("jquery");
import { Group } from "./Group";


export class Model {
  ////////////////////////////////////////////////////////////
  // Properties
  // Some of these are constants, others record the state of
  // the notification.
  ////////////////////////////////////////////////////////////

  // Dynamic
  private _content: HTMLDivElement;

  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor(
    name: string,
    currentDf: string,
    originalDf: string,
    groups: Group[]
  ) {
    this._content = this._generateBaseElement(
            name,
            currentDf,
            originalDf,
            groups
    );
  }

  ////////////////////////////////////////////////////////////
  // Helper functions
  // Low-level functions that tend to be repeated often
  ////////////////////////////////////////////////////////////

  private _generateBaseElement(
    name: string,
    currentDf: string,
    originalDf: string,
    groups: Group[]
  ): HTMLDivElement {
    var elem = $.parseHTML(`
    <div class="model">
        <h3>${name}</h3>
        <p>Model evaluated on: <span class="code-snippet-minor">${currentDf}</span>, using sensitive columns from <span class="code-snippet-minor">${originalDf}</span></p>
        <div class="groups-container">
            
        </div>
    </div>
    `);
    for(var group of groups) {
        $(elem).find(".groups-container").append($(group.export()))
    }
    var htmlElem = elem[1] as any as HTMLDivElement;
    return htmlElem;
  }


  ////////////////////////////////////////////////////////////
  // Abstractions
  ////////////////////////////////////////////////////////////

  // Given a string of the header's content, this will automatically add
  // a header to the note at the bottom of the note's content.
  export(): HTMLDivElement {
    return this._content;
  }
}
