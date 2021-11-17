import { PopupNotification } from "./PopupNotification";
import { ProtectedData } from "./ProtectedData";
import $ = require('jquery');


export class ProtectedColumnNote extends PopupNotification {


    ////////////////////////////////////////////////////////////
    // Properties
    // Some of these are constants, others record the state of
    // the notification. 
    ////////////////////////////////////////////////////////////
  
    private _data : ProtectedData[];
    private _dfs : string[];

    ////////////////////////////////////////////////////////////
    // Constructor
    ////////////////////////////////////////////////////////////

    constructor(notices : any[]) {
        super("protected", true, "Protected Columns Note")
        this._data = []
        this._dfs = []
        for(var x = 0; x < notices.length; x++) {
            this._data.push(new ProtectedData(notices[x]))
            this._dfs.push(notices[x]["df"])
        }
        super.addRawHtmlElement(this._generateBaseNote(this._dfs));
    }

    ////////////////////////////////////////////////////////////
    // Helper functions
    // Low-level functions that tend to be repeated often
    ////////////////////////////////////////////////////////////

    private _generateBaseNote(dfs : any[]) : HTMLElement {
        var dfString = "";
        for(var x = 0; x < dfs.length; x++) {
            dfString += `<div class="dfs">
            <div class="df shadowDefault" id=${dfs[x]}>
                <h1>Within ${dfs[x]}</h1>
                <div class="sensitivity shadowDefault">
                    <h2>Column Sensitivity</h2>
                    <!-- Dropdown from https://codepen.io/havardob/pen/KKqYGYj -->
                    <!-- All columns go here, append to "sensitivity" -->
                </div>
                <div class="column explorer shadowDefault textAlignCenter">
                </div>
            </div>
        </div>`
        }
        var elem = $.parseHTML(`
            <div class="promptMl protectedColumns">
                <h1>Protected Column Note</h1>
                <div class="intro">
                    <p>Lorem ipsum dolor sit amet, consectetur adipisicing elit. Inventore expedita error, voluptatibus at nulla iusto fugit consequuntur nam cumque neque non accusamus omnis laboriosam autem dolorum corporis rerum repellat quaerat!
                    <br>Lorem ipsum dolor sit amet, consectetur adipisicing elit. Inventore expedita error, voluptatibus at nulla iusto fugit consequuntur nam cumque neque non accusamus omnis laboriosam autem dolorum corporis rerum repellat quaerat!
                    <br>Lorem ipsum dolor sit amet, consectetur adipisicing elit. Inventore expedita error, voluptatibus at nulla iusto fugit consequuntur nam cumque neque non accusamus omnis laboriosam autem dolorum corporis rerum repellat quaerat!</p>
                    <div class="sources shadowDefault">
                        <a href="#"><h2 class="shadow">Resource 1</h2></a>
                        <a href="#"><h2 class="shadow">Resource 2</h2></a>
                        <a href="#"><h2 class="shadow">Resource 3</h2></a>
                    </div>
                </div>${dfString}
            </div>
        `);
        var htmlElem = elem[1] as any as HTMLElement;
        for(var x = 0; x < this._data.length; x++) {
            htmlElem.querySelector(`#${this._data[x]["df"]} .sensitivity`).appendChild(this._data[x].exportColumns());
            htmlElem.querySelector(`#${this._data[x]["df"]} .explorer`).appendChild(this._data[x].exportExplorer());
        }
        return htmlElem;
    }

    ////////////////////////////////////////////////////////////
    // Abstractions
    // Tries to make note generation more intuitive and consistent across
    // different note types and styles.
    ////////////////////////////////////////////////////////////

    public _populateNote() : HTMLDivElement {
        var elem = document.createElement("div");
        elem.classList.add("promptMl");
        elem.style.cssText = "padding: 15px; overflow: scroll;";
        return elem;
    }

    export() : HTMLDivElement {
        return this._content // doesn't clone, returns the actual element -- prevents the event listeners from being removed
    }
}