import {
  JupyterFrontEnd
} from "@jupyterlab/application"
/*
import {
  Widget
} from "@lumino/widgets"
*/
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
  OutputMetadata,
  IExecuteResult
} from "@jupyterlab/nbformat" 

import {
  Listener,
} from "./cell-listener";
/*
import {
  CodeCellClient
} from "./client";

import {
  ServerConnection
} from "@jupyterlab/services";
*/
export class Prompter {
  /*
   * This generates prompts for notebook cells on notification of 
   * new data or a new model
   */
  private _tracker : INotebookTracker;
  constructor(listener : Listener, tracker : INotebookTracker, app : JupyterFrontEnd, factory : NotebookPanel.IContentFactory) {
    this._tracker = tracker;
    listener.infoSignal.connect(
        (sender : Listener, output : any) => {
          this._onInfo(output)});
  }
  
  private appendMsg(cell : Cell, msg : string) {
    var outputmodel : IOutputAreaModel = (cell as CodeCell).model.outputs;
    if (outputmodel.length > 0) {
      var new_output = {output_type : "execute_result",
                        execution_count : outputmodel.get(0).executionCount,
                        data : {"text/html" : msg},
                        metadata : (outputmodel.get(0).metadata as OutputMetadata)}; 
      outputmodel.add((new_output as IExecuteResult)); 
    } else {
      let blank_metadata : OutputMetadata;
      var new_output = {output_type : "execute_result",
                        execution_count : (cell as CodeCell).model.executionCount, 
                        data : {"text/html" : msg},
                        metadata : blank_metadata}
      outputmodel.add((new_output as IExecuteResult)); 
    } 
  } 
  private _onInfo(info_object : any) {
    var cell : Cell = this._getCell(info_object["cell"], this._tracker);
    
    if (info_object["type"] == "resemble") {
      let msg : string = "<div>Column <b>"+info_object["column"]+"</b> resembles "+info_object["category"] +"</div>";
      this.appendMsg(cell, msg); 
    }
    if (info_object["type"] == "wands") { // categorical variance
      let msg : string = "<div> The "+info_object["op"] + " of column <b>";
      msg += info_object["num_col"] + "</b> has variance of " + info_object["var"];
      msg += " with <b>" + info_object["cat_col"] + "</b></div>";
      msg += "<div> This means that is "+info_object["rank"]+" out of " + info_object["total"] + "</div>";
      this.appendMsg(cell, msg); 
    }
    if (info_object["type"] == "cups") {// correlation
      let msg : string = "<div><b>"+info_object["col_a"] +"</b> is has a correlation of "+info_object["strength"];
      msg += " with <b>"+info_object["col_b"] + "</b></div>";
      msg += "<div>This means that it is the "+info_object["rank"] + " out of " +info_object["total"] +"</div>";
      this.appendMsg(cell, msg);
    }
    if (info_object["type"] == "pentacles") { // extreme values
    }
    if (info_object["type"] == "swords") { // undefined
    }
  } 

/*  private _onDataNotify(data_object : any) {

    var data_entries : any = Object.keys(data_object); // each key a data variable

    for (var data_name of data_entries) {

      var data = data_object[data_name];

      if ("cell" in data) {
        console.log("[PROMPTML] searching for cell", data["cell"]);
        // get cell
        var cell : Cell = this._getCell(data["cell"], this._tracker);


        if (cell == null) { return; };
	    if (data["source"] == "") { return; };

//        var outputmodel : IOutputAreaModel = (cell as CodeCell).model.outputs;
       
 //       const n : number = outputmodel.length;
        this.appendMessage(cell, "<div>Hello world</div>"); 
//        for (var i : number = 0; i < n; i++) {
//          console.log("output model content: ", outputmodel.get(i));
/*          let new_output : IExecuteResult = new AddedOutput(outputmodel.get(i).executionCount, 
                                                            outputmodel.get(i).data,
                                                            outputmodel.get(i).metadata);*/

//          var new_output = {output_type : "execute_result", 
//                            execution_count : outputmodel.get(i).executionCount,
//                            data : outputmodel.get(i).data,
//                            metadata : outputmodel.get(i).metadata};
                            
//          outputmodel.add((new_output as IExecuteResult));  // this worked, so going to refine technique now
//        }

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

/*
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
*/
/*
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
*/
/*
  private _makeDiv(classnames : string) {
    let elt = document.createElement("div");
    elt.className = classnames;
    return elt;
  }
*/
/*
  private _onModelNotify(models : any) {
    // var cell : Cell = this._getCell(models["cell"], this._tracker);
  }
*/
  private _getCell(id : string, tracker : INotebookTracker) : Cell {

    var nb : Notebook = tracker.currentWidget.content;

    for (let i = 0; i < nb.widgets.length; i++) {
      if (nb.widgets[i].model.id == id) {
        return nb.widgets[i];
      }
    }

    return null;
  }
/*
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
*/
/*
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
*/
}
/*
function _minimizeForm(prompt_div : HTMLElement, min_div : HTMLElement) {

  prompt_div.style.display = "none";
  min_div.style.display = "block" 

  min_div.onclick = function() { _maximizeForm(prompt_div, min_div) };
}
 
function _maximizeForm(prompt_div : HTMLElement, min_div : HTMLElement) {

  prompt_div.style.display = "block";
  min_div.style.display = "none";

}
*/
