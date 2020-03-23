import {
  INotebookTracker,
  Notebook, 
} from "@jupyterlab/notebook";

import { 
  Cell,
} from "@jupyterlab/cells"

import {
  Listener,
} from "./cell-listener"

export class Prompter {
  /*
   * This generates prompts for notebook cells on notification of 
   * new data or a new model
   */
  private _tracker : INotebookTracker;
  constructor(listener : Listener, tracker : INotebookTracker) {
    this._tracker = tracker;
    listener.datasignal.connect(
      (sender : Listener, output : any) => {
        this._onDataNotify(output);});
    listener.modelsignal.connect(
      (sender : Listener, output : any) => {
        this._onModelNotify(output);});
  }
   
  private _onDataNotify(data_object : any) {

    var data_entries : any = Object.keys(data_object); // each key a data variable

    for (var data_name of data_entries) {

      var data = data_object[data_name];

      if ("cell" in data) {
        console.log("[PROMPTML] searching for cell", data["cell"]);
        // get cell
        var cell : Cell = this._getCell(data["cell"], this._tracker);

        if (cell == null) { return; };
	if (data["source"] == "") { return; };

        console.log("[PROMPTML] found cell"); 
        let prompt_container = this._makeDiv("p-Widget p-Panel jp-prompt-Wrapper");
      
        let collapser_holder = this._makeDiv("p-Widget jp-Collapser jp-OutputCollapser jp-prompt-collapser");
        let collapser_final = this._makeDiv("jp-Collapser-child");

        collapser_holder.appendChild(collapser_final);
 
        prompt_container.appendChild(collapser_holder)

        let prompt_area = this._makeDiv("p-Widget jp-OutputArea jp-prompt-area");
	let prompt_child = this._makeDiv("p-Widget p-Panel jp-OutputArea-child");
	prompt_child.appendChild(this._makeDiv("p-Widget jp-OutputPrompt jp-OutputArea-prompt"));
	let prompt_final = this._makeDiv("p-Widget jp-RenderedText jp-prompt-area");
        prompt_final.innerText = "Using data from " + data["source"];

	prompt_child.appendChild(prompt_final);

	prompt_area.appendChild(prompt_child);
        prompt_container.appendChild(prompt_area);

	//console.log("[PROMPTML] attaching new node to cell");
        //console.log("[PROMPTML] cell node type", cell.node.className);
	//console.log("[PROMPTML] cell has children ", cell.node.children);

        let sibling = cell.node.children[3];
        cell.node.insertBefore(prompt_container, sibling);
      }
    }
    // get 
  }
  private _makeDiv(classnames : string) {
    let elt = document.createElement("div");
    elt.className = classnames;
    return elt;
  }

  private _onModelNotify(models : any) {
    // var cell : Cell = this._getCell(models["cell"], this._tracker);
  }

  private _getCell(id : string, tracker : INotebookTracker) : Cell {

    var nb : Notebook = tracker.currentWidget.content;

    for (let i = 0; i < nb.widgets.length; i++) {
      if (nb.widgets[i].model.id == id) {
        return nb.widgets[i];
      }
    }

    return null;
  }
}

