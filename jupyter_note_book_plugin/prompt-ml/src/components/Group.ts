import $ = require("jquery");

export class Group {
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
    precision: string,
    recall: string,
    f1Score: string,
    fpr: string,
    fnr: string
  ) {
    this._content = this._generateBaseElement(
            name,
            precision,
            recall,
            f1Score,
            fpr,
            fnr
    );
  }

  ////////////////////////////////////////////////////////////
  // Helper functions
  // Low-level functions that tend to be repeated often
  ////////////////////////////////////////////////////////////

  private _generateBaseElement(
    name: string,
    precision: string,
    recall: string,
    f1Score: string,
    fpr: string,
    fnr: string
  ): HTMLDivElement {
    var elem = $.parseHTML(`
    <div class="group">
        <h4>${name}</h4>
        <p>Precision: ${precision}</p>
        <p>Recall: ${recall}</p>
        <p>F1 Score: ${f1Score}</p>
        <p>FPR: ${fpr}</p>
        <p>FNR: ${fnr}</p>
    </div>`);
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
