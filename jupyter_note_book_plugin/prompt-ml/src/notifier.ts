import {
  find
} from "@lumino/algorithm"

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
  IOutputAreaModel, OutputPrompt, OutputArea
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
    let ins_n : number = outputmodel.length;

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
    
    // get the OutputPrompt and overwrite
    this._overwritePrompt(cell as CodeCell, ins_n);

  }
  
  private _isOp(w : Widget) {
    return w instanceof OutputPrompt;
  }

  private _findOp(cell : CodeCell, ins_index : number) : OutputPrompt {

    let tgt_op : OutputArea = (cell.outputArea.widgets[ins_index] as OutputArea);
    let output_prompt : OutputPrompt = (find(tgt_op.widgets, this._isOp) as OutputPrompt)
    
    return output_prompt;
  }
 
  private _overwritePrompt(cell : CodeCell, ins_index : number) {
    // overwrite the output prompt for the additional commentary
    let output_prompt : OutputPrompt = this._findOp(cell, ins_index);
    if (output_prompt && (output_prompt.executionCount == cell.model.executionCount)) {
        output_prompt.node.textContent = "[!]:"; 
    }
  }

  private _routeNotice(notice : any) {
    if (notice["type"] == "resemble") {
      return this._makeResembleMsg(notice["df"], notice["col"]).outerHTML;
    }
    if (notice["type"] == "variance") {
      return this._makeVarMsg(notice["zip1"], notice["zip2"], notice["demo"]).outerHTML;
    }
    if (notice["type"] == "outliers") {
      return this._makeOutliersMsg(notice["col_name"], notice["value"], notice["std_dev"]).outerHTML;
    }
    if (notice["type"] == "model_perf") {
      return this._makePerformanceMsg(notice).outerHTML;
    }
  }

  private _onInfo(info_object : any) {

    var cell : Cell = this._getCell(info_object["cell"], this._tracker);

    if (info_object["type"] == "multiple") {
      for (let key of Object.keys(info_object["info"])) {
        cell = this._getCell(key, this._tracker);
        for (let notice of info_object["info"][key]) {
          let msg : string = this._routeNotice(notice);
          if (msg) { this.appendMsg(cell, msg); }
        } 
      }   
    }
  
    if (info_object["type"] == "resemble") {
      let msg : string = "<div>Column <b>"+info_object["column"]+"</b> resembles "+info_object["category"] +"</div>";
      this.appendMsg(cell, msg); 
    }
    if (info_object["type"] == "wands") { // categorical variance
      let msg : string = this._makeWandsMsg(info_object["op"], 
                                            info_object["num_col"],
                                            info_object["var"], 
                                            info_object["cat_col"],
                                            info_object["rank"],
                                            info_object["total"]).outerHTML;
      this.appendMsg(cell, msg); 
    }
    if (info_object["type"] == "cups") {// correlation
      let msg : string = this._makeCupsMsg(info_object["col_a"], info_object["col_b"],
                                           info_object["strength"], info_object["rank"]).outerHTML;
      this.appendMsg(cell, msg);
    }
    if (info_object["type"] == "pentacles") { // extreme values
      let msg : string = this._makePentaclesMsg(info_object["col"],
                                                info_object["strength"],
                                                info_object["element"],
                                                info_object["rank"]).outerHTML;
     
      this.appendMsg(cell, msg);
    }
    if (info_object["type"] == "swords") { // undefined
      let msg : string = this._makeSwordsMsg(info_object["col"], info_object["strength"],
                                             info_object["rank"]).outerHTML;
      this.appendMsg(cell, msg);
    }
  } 
  
  private _makeContainer(df_name? : string)  : [HTMLDivElement, HTMLDivElement] {
    /* 
    the template for prompt containers returns top level container and element that 
    the notification should be put into
    */
    let elt : HTMLDivElement = document.createElement("div");
    elt.className = "jp-PromptArea";  

    let spacer = document.createElement("div");
    spacer.className = "jp-PromptArea-spacer";

    let area : HTMLDivElement = document.createElement("div");
    area.className = "jp-PromptArea-Prompt";

    let heading = document.createElement("h1");
    
    if (df_name) {
      heading.innerText = "A fact about "+df_name;
    } else { heading.innerText = "A fact about the data"; }
   
    area.appendChild(heading);
 
    elt.appendChild(spacer);
    elt.appendChild(area);
 
    return [elt, area]; 
  }
 
  private _makeWandsMsg(op : string, num_col : string, variance : string, 
                        cat_col : string, rank : number, total : number) {
    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");
    let var_line_3 = document.createElement("p");

    var_line_1.innerHTML = "The <b>"+op+"</b> of <b>"+num_col+"</b> broken down by ";
    var_line_1.innerHTML += "<b>"+cat_col +"</b> has variance "+variance.slice(0,5);

    var_line_2.innerHTML = "There are "+ (rank - 1).toString() + " combinations of variables with higher variance";
    
    let link = document.createElement("a");
    link.href = "https://en.wikipedia.org/wiki/Variance";

    link.innerText = "What is variance?";
    var_line_3.appendChild(link);
    
    var [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);
    area.appendChild(var_line_3);

    return body;     
  }

  private _makeCupsMsg(col_a : string, col_b : string, strength : string, rank : number) {

    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");
    let var_line_3 = document.createElement("p");

    var_line_1.innerHTML = "<b>"+col_a+"</b> has a correlation with <b>"+col_b+"</b>";
    var_line_1.innerHTML += " with a strength of "+strength.slice(0,5);
    var_line_2.innerHTML = "There are "+ (rank - 1).toString() + " combinations of variables with higher correlation strength";
    
    let link = document.createElement("a");
    link.href = "https://en.wikipedia.org/wiki/Pearson_correlation_coefficient";

    link.innerText = "What is correlation?";
    var_line_3.appendChild(link);
    
    let [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);
    area.appendChild(var_line_3);

    return body;     
  }

  private _makePentaclesMsg(col : string, strength : string, 
                            element : string, rank : number) {

    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");
    let var_line_3 = document.createElement("p");

    var_line_1.innerHTML = "<b>"+col+"</b> contains the value <b>"+element+"</b>";
    var_line_1.innerHTML += " which is "+strength.slice(0,5)+" standard deviations out from the column mean";
    var_line_2.innerHTML = "There are "+ (rank - 1).toString() + " other variables with more extreme outliers";
    
    let link = document.createElement("a");
    link.href = "https://en.wikipedia.org/wiki/Standard_score";

    link.innerText = "What is an outlier?";
    var_line_3.appendChild(link);
    
    let [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);
    area.appendChild(var_line_3);

    return body;     
  }

  private _makeSwordsMsg(col : string, strength : string, rank : number) {

    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");

    let prop : number = parseFloat(strength);
    let pct : number = prop*100;

    var_line_1.innerHTML = pct.toString().slice(0,5)+"% of entries in <b>"+col+"</b> are null";

    var_line_2.innerHTML = "There are "+ (rank - 1).toString() + " other variables with more null entries";
    
    let [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);

    return body;
  }
  private _makeResembleMsg(df_name : string, col_name : string) {

    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");

    var_line_1.innerHTML = "The dataframe <b>"+df_name+"</b> contains a column <b>"+col_name+"</b>";

    var_line_2.innerHTML = "Using this column may be discriminatory";
    
    var [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);

    return body;     
  }

  private _makeVarMsg(zip1 : string, zip2 : string, demo : any) {

    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");

    var_line_1.innerHTML = "Zip code <b>"+zip1+"</b> is "+demo[zip1]+"% black";
    var_line_2.innerHTML = "Zip code <b>"+zip2+"</b> is "+demo[zip2]+"% white";

    var [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);

    return body;
  }
  private _makeOutliersMsg(col_name : string, value : number, std_dev : number) {

    let var_line_1 = document.createElement("p");
    let var_line_2 = document.createElement("p");

    var_line_1.innerHTML = "The column <b>"+col_name+"</b> contains values greater than "+value;
    var_line_2.innerHTML = value + " is "+std_dev.toString().slice(0,5)+" standard deviations above the average for that column";

    var [body, area] = this._makeContainer();
    area.appendChild(var_line_1);
    area.appendChild(var_line_2);

    return body;
  }

  private _makePerformanceMsg(notice : any) {

    let msg_l1 = document.createElement("p");
    msg_l1.innerHTML = "The model "+notice["model_name"]+" has an accuracy of "+notice["acc"];
    let msg_l2 = document.createElement("p");
    msg_l2.innerHTML = "The mistakes it makes break down as follows";

    let table_elt = document.createElement("table");
    let header = document.createElement("tr");

    header.appendChild(document.createElement("th"));
    header.appendChild(document.createElement("th"));

    let fpr_header = document.createElement("th");
    let fnr_header = document.createElement("th");

    fpr_header.innerHTML = "Pr[&#374;="+notice["values"]["pos"] +"|Y="+notice["values"]["neg"]+"]";
    fnr_header.innerHTML = "Pr[&#374;="+notice["values"]["neg"] +"|Y="+notice["values"]["pos"]+"]";

    header.appendChild(fpr_header);
    header.appendChild(fnr_header);

    table_elt.appendChild(header);

    for (let col_name of Object.keys(notice["columns"])) {

      let col_values = Object.keys(notice["columns"][col_name])
    
      for (let i = 0; i < col_values.length; i++) {

        let row = document.createElement("tr");

        if (i == 0) {
          let col_name_entry = document.createElement("th");
          col_name_entry.setAttribute("rowspan", col_values.length.toString());
          col_name_entry.innerHTML = col_name;
          row.appendChild(col_name_entry);
        }

        let value_name = document.createElement("td");
        value_name.innerHTML = col_values[i];
        row.appendChild(value_name);

        let rates_obj = notice["columns"][col_name][col_values[i]];

        let fpr_entry = document.createElement("td");
        fpr_entry.innerHTML = rates_obj["fpr"].toFixed(3);
        row.appendChild(fpr_entry);

        let fnr_entry = document.createElement("td");
        fnr_entry.innerHTML = rates_obj["fnr"].toFixed(3);
        row.appendChild(fnr_entry);

        table_elt.appendChild(row);
      }  
    }

    var [body, area] = this._makeContainer();

    area.appendChild(msg_l1);
    area.appendChild(msg_l2);
    area.appendChild(table_elt);

    return body; 
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
