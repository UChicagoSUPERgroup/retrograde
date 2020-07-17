import {
  JupyterFrontEnd
} from "@jupyterlab/application"

import {
  Widget
} from "@lumino/widgets"

import {
  INotebookTracker,
  Notebook,
  NotebookPanel,
} from "@jupyterlab/notebook";

import { 
  Cell, CodeCell,
} from "@jupyterlab/cells";

import {
  IOutputAreaModel,
} from "@jupyterlab/outputarea";

import {
//  ExecutionCount,
//  IMimeBundle,
//  OutputMetadata,
  IExecuteResult
} from "@jupyterlab/nbformat" 

import {
  Listener,
} from "./cell-listener";

import {
  CodeCellClient
} from "./client";

import {
  ServerConnection
} from "@jupyterlab/services";

export class Prompter {
  /*
   * This generates prompts for notebook cells on notification of 
   * new data or a new model
   */
  private _tracker : INotebookTracker;
  constructor(listener : Listener, tracker : INotebookTracker, app : JupyterFrontEnd, factory : NotebookPanel.IContentFactory) {
    this._tracker = tracker;
    listener.newsignal.connect(
      (sender : Listener, output : any) => {
        this._onDataNotify(output);});
    listener.changesignal.connect(
      (sender : Listener, output : any) => {
        this._onModelNotify(output);});


    // list widgets
    app.restored.then( function() {

      let widgets = app.shell.widgets("main");
      let widget : Widget | undefined;
      let panel : NotebookPanel;

      while (true) {
        widget = widgets.next();
        if (widget == undefined) { break; }
        if (widget.constructor.name == "NotebookPanel") { break; }
        console.log("widget ", widget.constructor.name); // is a NotebookPanel
      }

      panel = widget as NotebookPanel;
      console.log(panel.content.contentFactory.constructor.name); 
//      panel.content.contentFactory = new CellFactory();
    }) 

     // next want to override widget cell factory to produce our own
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

        var outputmodel : IOutputAreaModel = (cell as CodeCell).model.outputs;
       
        const n : number = outputmodel.length;
 
        for (var i : number = 0; i < n; i++) {
          console.log("output model content: ", outputmodel.get(i));
/*          let new_output : IExecuteResult = new AddedOutput(outputmodel.get(i).executionCount, 
                                                            outputmodel.get(i).data,
                                                            outputmodel.get(i).metadata);*/

          var new_output = {output_type : "execute_result", 
                            execution_count : outputmodel.get(i).executionCount,
                            data : outputmodel.get(i).data,
                            metadata : outputmodel.get(i).metadata};
                            
          outputmodel.add((new_output as IExecuteResult));  // this worked, so going to refine technique now
        }


        //let test_output = IExecuteResult // todo: implement non-blocking type of output, write that in s.t. it gets rendered

        //let prompt_container = this._makeDiv("p-Widget p-Panel jp-prompt-Wrapper");
        //let collapser_holder = this._makeDiv("p-Widget jp-Collapser jp-OutputCollapser jp-prompt-collapser");
        //let collapser_final = this._makeDiv("jp-Collapser-child");
        //collapser_holder.appendChild(collapser_final);
        //prompt_container.appendChild(collapser_holder)

        //let prompt_area = this._makeDiv("p-Widget jp-OutputArea jp-prompt-area");
	    //let prompt_child = this._makeDiv("p-Widget p-Panel jp-OutputArea-child");
    	//prompt_child.appendChild(this._makeDiv("p-Widget jp-OutputPrompt jp-OutputArea-prompt"));
    	//let prompt_final = this._makeDiv("p-Widget jp-RenderedText jp-prompt-area");
        //prompt_final.innerText = "Using data from " + data["source"];
	    //prompt_child.appendChild(prompt_final);
	    //prompt_area.appendChild(prompt_child);
        //prompt_container.appendChild(prompt_area);

    	//console.log("[PROMPTML] attaching new node to cell");
        //console.log("[PROMPTML] cell node type", cell.node.className);
    	//console.log("[PROMPTML] cell has children ", cell.node.children);


        let text = this._newDataText();

        let additional_info = { 
            "source" : data["source"],
            "type" : "new_data"};

        let new_data_prompt = this._makeForm(text, data["cell"], additional_info);
        let sibling = cell.node.children[3];
        cell.node.insertBefore(new_data_prompt, sibling);
      }
    }
  }

  private _form_onclick_factory(input_area : HTMLTextAreaElement, 
                                cell : string, prompt_div : HTMLElement, 
                                min_div : HTMLElement,
                                additional_info? : any) : () => void{
   
          var output : any = {
            "cell" : cell,
          };
          if (additional_info) { 
            output = { ...output, ...additional_info};
            console.log("[PROMPT-ML tried to add ",additional_info," output is ",output);
          }
 
        let new_data_form = function() {
            var client : CodeCellClient = new CodeCellClient();
            output["input"] = input_area.value;
            console.log("[PROMPT-ML] sending ", output);
            client.request("exec", "POST", JSON.stringify(output),
                ServerConnection.defaultSettings); 
            _minimizeForm(prompt_div, min_div);
        }

        return new_data_form;
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

  private _makeForm(question_text : HTMLElement, cell : string, additional_info? : any) : HTMLElement {
    // make a form with text input
    let prompt_container = this._makeDiv("p-Widget p-Panel jp-prompt-Wrapper");
    let collapser_holder = this._makeDiv("p-Widget jp-Collapser jp-OutputCollapser jp-prompt-collapser");
    let collapser_final = this._makeDiv("jp-Collapser-child");
        
    collapser_holder.appendChild(collapser_final);
    prompt_container.appendChild(collapser_holder)

    let prompt_area = this._makeDiv("p-Widget jp-OutputArea jp-prompt-area");
	let prompt_child = this._makeDiv("p-Widget p-Panel jp-PromptArea-child");
	prompt_child.appendChild(this._makeDiv("p-Widget jp-OutputPrompt jp-OutputArea-prompt"));
	let prompt_final = this._makeDiv("p-Widget jp-RenderedText jp-prompt-area");

    // minimized view
    let min_child = this._makeDiv("p-Widget p-panel jp-PromptArea-child");
    let bar = document.createElement("hr");
    min_child.appendChild(bar);
    min_child.style.display = "none";
    prompt_area.appendChild(min_child); 

    prompt_final.appendChild(question_text);
	prompt_child.appendChild(prompt_final);
	prompt_area.appendChild(prompt_child);
    prompt_container.appendChild(prompt_area);

    let input_area = this._makeDiv("p-Widget jp-InputArea jp-PromptInputArea");
    let input_field = document.createElement("textarea");

    input_area.appendChild(input_field);
    prompt_child.appendChild(input_area);

    let button = document.createElement("button");
    button.innerText = "Submit";
    button.className = "jp-prompt-input-button";
    button.onclick = this._form_onclick_factory(input_field, cell, prompt_child, min_child, additional_info);
    prompt_child.appendChild(button);

    return prompt_container;
  }

  private _newDataText() {

    var prompt_container = this._makeDiv("p-Widget jp-Cell");

    var prompt_text = document.createElement("p");
    var text : string = "This looks like a new dataset. Could you tell us a little bit about:"
    prompt_text.innerText = text;
    prompt_container.appendChild(prompt_text);

    var elts = document.createElement("ul");
    var q1 = document.createElement("li");
    q1.innerText = "Who produced this data? Who curated it? Are they the same?";

    var q2 = document.createElement("li");
    q2.innerText = "Why was this dataset produced?";
    
    var q3 = document.createElement("li");
    q3.innerText = "Are there processes relevant to data subjects that might not be explicitly captured in this dataset?";

    var q4 = document.createElement("li");
    q4.innerText = "Do you know of other datasets capturing the same phenomena you are interested in? If so, why this dataset and not others?";

    elts.appendChild(q1);
    elts.appendChild(q2);
    elts.appendChild(q3);
    elts.appendChild(q4);

    prompt_container.appendChild(elts);

    return prompt_container;
  }
}

function _minimizeForm(prompt_div : HTMLElement, min_div : HTMLElement) {

  prompt_div.style.display = "none";
  min_div.style.display = "block" 

  min_div.onclick = function() { _maximizeForm(prompt_div, min_div) };
}
 
function _maximizeForm(prompt_div : HTMLElement, min_div : HTMLElement) {

  prompt_div.style.display = "block";
  min_div.style.display = "none";

}
/*
class AddedOutput implements IExecuteResult {

  output_type : "execute_result";
  execution_count : ExecutionCount;
  data : IMimeBundle;
  metadata : OutputMetadata;

  constructor(cell_count : ExecutionCount, 
              data? : IMimeBundle,
              metadata? : OutputMetadata) {
    this.execution_count = cell_count;
    
    if (!data) {
    } 

    this.data["text/html"] += "<div> Hello world </div>";

    if (!metadata) {
    }
  }
}
/*
class CellFactory extends NotebookPanel.ContentFactory {
  createCodeCell(options : CodeCell.IOptions, parent : StaticNotebook) : CodeCell {
    console.log("created code cell")
    return super.createCodeCell(options, parent);
  }
  
}*/
