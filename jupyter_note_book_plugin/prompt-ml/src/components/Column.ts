import $ = require('jquery');

export class Column {

    ////////////////////////////////////////////////////////////
    // Properties
    // Some of these are constants, others record the state of
    // the notification. 
    ////////////////////////////////////////////////////////////
  
    // Given by user
    name: string;
    sensitive: boolean;
    typeOfSensitivity: string;
    df: string;
    potentialSensitivities : string[];
    // Dynamic
    private _onClickEvent : any;
    private _content: HTMLDivElement;
    private _index : number;

    ////////////////////////////////////////////////////////////
    // Constructor
    ////////////////////////////////////////////////////////////

    constructor(name: string, sensitive: boolean, typeOfSensitivity: string, df: string, potentialSensitivities : string[], index : number) {
      this.name = name;
      this.sensitive = sensitive;
      this.typeOfSensitivity = typeOfSensitivity;
      this.df = df;
      this.potentialSensitivities = potentialSensitivities;
      this._onClickEvent = function() : void {console.log("uninitialized")}
      this._index = index;
      this._content = this._generateBaseElement();
    }
  
    ////////////////////////////////////////////////////////////
    // Helper functions
    // Low-level functions that tend to be repeated often
    ////////////////////////////////////////////////////////////

    private _generateElement(type : string, content : string) : HTMLElement {
      var elem = document.createElement(type);
      elem.innerHTML = content;
      return elem;
    }
  
    private _generateBaseElement() : HTMLDivElement {
      var elem = $.parseHTML(`
      <div class="dfColumn">
        <h3>${this.name} </h3>
        <fieldset>
          <details>
            <summary class="shadow ${(this.sensitive) ? "sensitive" : "nonsensitive"}">${this.typeOfSensitivity} <i class="ph-caret-down-bold"></i></summary>
              <div class="sensitivities">
              </div>
            </details>
        </fieldset>
      </div>`);
      var htmlElem =  elem[1] as any as HTMLDivElement;
      htmlElem.onclick = (event) => {this._columnSelected(this, event)};
      htmlElem.querySelector(".sensitivities").appendChild(this._generatePotentialSensitivites())
      return htmlElem;
    }

    private _generatePotentialSensitivites() : HTMLElement {
      var generated = this._generateElement("div", "")
      for(var x = 0; x < this.potentialSensitivities.length; x++) {
        var sensitivity = this.potentialSensitivities[x];
        generated.appendChild($.parseHTML(`<label><input type="radio" name="${sensitivity.toLowerCase()}" /><span class="typeOfSensitivity" id="${sensitivity}""}>${sensitivity}</span></label>`)[0] as HTMLElement);
      }
      return generated;
    }

    private _columnSelected(col : Column, event : any) {
      var fireOnChanged : Function = col._onClickEvent;
      if(event.target.classList.contains("typeOfSensitivity")) {
        var newSensitivity = event.target.id
        fireOnChanged(this.name, this.df, newSensitivity, this._index);
      }
    }

    onChange(f : Function) {
      this._onClickEvent = f;
    }
  
    ////////////////////////////////////////////////////////////
    // Abstractions
    ////////////////////////////////////////////////////////////
  
    // Given a string of the header's content, this will automatically add
    // a header to the note at the bottom of the note's content.
    export() : HTMLDivElement  {
      return this._content;
    }
  
  }