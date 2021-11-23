import $ = require('jquery');

export class Explorer {

    ////////////////////////////////////////////////////////////
    // Properties
    // Some of these are constants, others record the state of
    // the notification. 
    ////////////////////////////////////////////////////////////
  
    // Given by user
    columns : string[]
    df : string;
    // Dynamic
    private _content: HTMLDivElement;
    private _onClickEvent : any;

    ////////////////////////////////////////////////////////////
    // Constructor
    ////////////////////////////////////////////////////////////

    constructor(columns : string[], df : string) {
      this.columns = columns;
      this.df = df;
      this._content = this._generateBaseElement();
      this._onClickEvent = function() : void {console.log("uninitialized")}
    }
  
    ////////////////////////////////////////////////////////////
    // Helper functions
    // Low-level functions that tend to be repeated often
    ////////////////////////////////////////////////////////////
  
    private _generateBaseElement() : HTMLDivElement {
      var elem = $.parseHTML(`
      <div>
        <h2>Column Explorer</h2>
          <fieldset>
              <details>
                  <summary class="shadow">Select
                      <i class="ph-caret-down-bold"></i>
                  </summary>
                  <div class="columns">
                      
                  </div>
              </details>
          </fieldset>
          <h3>Classification</h3>
          <p class="classification">Please select a column to begin..</p>
          <h3>Value Distributions</h3>
          <div class="value-container">
            <p class="values">Please select a column to begin.</p>
          </div>
        </div>`);
      var htmlElem = elem[1] as HTMLDivElement;
      htmlElem.onclick = (event) => {this._explorerChanged(this, event)};
      htmlElem.querySelector(".columns").appendChild(this._generateListOfColumns());
      return htmlElem;
    }

    private _generateListOfColumns() : HTMLDivElement {
      var generatedString = "<div>";
      for(var x = 0; x < this.columns.length; x++) {
        generatedString += `<label"><input type="radio" name="${x}" /><span class="columnOption" id=${x}>${this.columns[x]}</span></label>`;
      }
      generatedString += "</div>";
      return $.parseHTML(generatedString)[0] as HTMLDivElement;
    }

    private _explorerChanged(explorer : Explorer, event : any) {
      var fireOnChanged : Function = explorer._onClickEvent;
      console.log(fireOnChanged)
      console.log(event.target.classList)
      if(event.target.classList.contains("columnOption")) {
        var targetId = event.target.id
        fireOnChanged(targetId, explorer.df);
      }
    }

    onChange(f : Function) {
      this._onClickEvent = f;
    }
 
    ////////////////////////////////////////////////////////////
    // Abstractions
    // Tries to make note generation more intuitive and consistent across
    // different note types and styles.
    ////////////////////////////////////////////////////////////
  
    // Given a string of the header's content, this will automatically add
    // a header to the note at the bottom of the note's content.
    export() : HTMLDivElement  {
      return this._content;
    }
  
  }
