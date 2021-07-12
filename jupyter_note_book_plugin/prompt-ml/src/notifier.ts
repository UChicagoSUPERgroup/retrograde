
  import {
    JupyterFrontEnd
  } from "@jupyterlab/application"
  
  // import {
  //   INotebookTracker,
  //   Notebook,
  //   NotebookPanel,
  // } from "@jupyterlab/notebook";

  import {
    INotebookTracker,
    NotebookPanel,
  } from "@jupyterlab/notebook";
  
  // import { 
  //   Cell,
  // } from "@jupyterlab/cells";
  
  import {
    Listener,
  } from "./cell-listener";

  import $ = require('jquery');

  export class Prompter {
    /*
     * This generates prompts for notebook cells on notification of 
     * new data or a new model
     */
    // private _tracker : INotebookTracker;
    constructor(listener : Listener, tracker : INotebookTracker, app : JupyterFrontEnd, factory : NotebookPanel.IContentFactory) {
      // this._tracker = tracker;
      listener.infoSignal.connect(
          (sender : Listener, output : any) => {
            this._onInfo(output)});
    }
    
    private appendMsg(cell_id : string, kernel_id : string, msg : string, handedPayload : any) {
  
      // var outputmodel : IOutputAreaModel = (cell as CodeCell).model.outputs;
      // commented out -- 5/28 -- 5/28
      
      var newNote = $.parseHTML(msg)
      // remove duplicate notes; this will make it appear at the bottom of the list
      $(".prompt-ml-container > *").each( function() {
        if($(this)[0].isEqualNode(newNote[0])) $(this).remove()
      })

      // TO DO: change msg from a string to an actual html element, that way you don't need to do weird stuff w the css selectors
      $(".prompt-ml-container").prepend(newNote) // prepend vs append. prepend makes notes appear at the top, append at the bottom. to discuss during meeting

      // add animations
      $(newNote).find(".content").toggle()
      $(newNote).addClass("condensed").removeClass("expanded")
      $(newNote).click( function() {
        if( $(this).hasClass("condensed")) {
            $(this).removeClass("condensed")
            $(this).addClass("expanded")
            $(this).find("svg.expanded").toggle(true)
            $(this).find("svg.condensed").toggle(false)
            $(this).find(".content").toggle(true)
        } else {
            $(this).removeClass("expanded")
            $(this).addClass("condensed")
            $(this).find("svg.condensed").toggle(true)
            $(this).find("svg.expanded").toggle(false)
            $(this).find(".content").toggle(false)
        }
    })

      // add "more" button
      $(newNote).find(".content").append($.parseHTML("<div class=\"more\"><h2>MORE INFO</h2></div>"))
      $(newNote).find(".more").click( () => {
        // Payload must contain the structure of the popup to render
        if(handedPayload == {}) {
          var payload : object =  {
            "title": "Default Page",
            "htmlContent": $.parseHTML("<p>Testing...</p>"),
          }
        } else {
          payload = handedPayload
        }

        $(".prompt-ml-container").trigger("prompt-ml:note-added", { "payload": payload })
    })
  
    // add close button
      $(newNote).find(".close").click( function(e) {
        e.stopPropagation()
        var parentNote = $(this).parent().parent().parent()
        if(!($(parentNote).hasClass("wasClosed"))) {
          $(this).parent().parent().css("background-color", "#A3A3A3").find(".more h2").css("background-color", "#939393")
          $(".prompt-ml-container").append($(parentNote))
          
          if( $(parentNote).hasClass("expanded")) {
            // var expanded = $(parentNote).find("div.expanded")
            $(parentNote).removeClass("expanded")
            $(parentNote).addClass("condensed")
            $(parentNote).find("svg.condensed").toggle(true)
            $(parentNote).find("svg.expanded").toggle(false)
            $(parentNote).find(".content").toggle(false)
          }
          $(parentNote).addClass("wasClosed")
        } else {
          $(this).parent().parent().css("background-color", "#F0B744").find(".more h2").css("background-color", "#F1A204")
            $(".prompt-ml-container").prepend($(parentNote))
            $(parentNote).removeClass("wasClosed")
        }
      })
    }

    private _routeNotice(notice : any) {
      if (notice["type"] == "resemble") {
        var message = this._makeResembleMsg(notice["df"], notice["col"]);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "variance") {
        var message = this._makeVarMsg(notice["zip1"], notice["zip2"], notice["demo"]);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "outliers") {
        var message = this._makeOutliersMsg(notice["col_name"], notice["value"], notice["std_dev"], notice["df_name"]);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "model_perf") {
        var message = this._makePerformanceMsg(notice);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "eq_odds") {
        var message = this._makeEqOddsMsg(notice);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "proxy") {
        var message = this._makeProxyMsg(notice);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "missing") {
        var message = this._makeMissingMsg(notice);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1]
        return [stringHTML, object]
      } else {
        console.log("No notes generated", notice["type"], notice)
      }
    }
  
    private _onInfo(info_object : any) {

      if (info_object["type"] == "multiple") {
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        var notices = info_object["info"][cell_id]
        var proxies = []
        for (var x = 0; x < notices.length; x++) {
            if (notices[x]["type"] == "proxy") {
              proxies.push(notices[x]);
              continue;
            }
            var notice = notices[x]
            var noticeResponse = this._routeNotice(notice);
            if(noticeResponse == undefined) return
            let msg : string = noticeResponse[0] as string
            let popupContent : object = noticeResponse[1] as object
            if (msg) { this.appendMsg(cell_id, kernel_id, msg, popupContent); }
        }
        this._handleProxies(proxies)
      }
    
      if (info_object["type"] == "resemble") {
        let msg : string = "<div>Column <b>"+info_object["column"]+"</b> resembles "+info_object["category"] +"</div>";
        let payload = {}
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
      }
      if (info_object["type"] == "wands") { // categorical variance
        let responseMessage = this._makeWandsMsg(info_object["op"], 
                                              info_object["num_col"],
                                              info_object["var"], 
                                              info_object["cat_col"],
                                              info_object["rank"],
                                              info_object["total"]);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
      }
      if (info_object["type"] == "cups") {// correlation
        let responseMessage = this._makeCupsMsg(info_object["col_a"], info_object["col_b"],
                                             info_object["strength"], info_object["rank"]);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
      }
      if (info_object["type"] == "pentacles") { // extreme values
        let responseMessage = this._makePentaclesMsg(info_object["col"],
                                                  info_object["strength"],
                                                  info_object["element"],
                                                  info_object["rank"]);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
      }
      if (info_object["type"] == "swords") { // undefined
        let responseMessage = this._makeSwordsMsg(info_object["col"], info_object["strength"], info_object["rank"]);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
      }
    } 

    private _handleProxies(proxies : { [ key: string ] : any }[]) {
      console.log(proxies);
      var d : { [key : string ] : {[key: string] : string[]} } = {};
      for(var x = 0; x < proxies.length; x++) {
        var p : any = proxies[x];
        if(!(p["df"] in d)) d[p["df"]] = {"proxy_col_name": [], "sensitive_col_name": [], "p_vals": []};
        d[p["df"]]["proxy_col_name"].push(p["proxy_col_name"]);
        d[p["df"]]["sensitive_col_name"].push(p["sensitive_col_name"]);
        d[p["df"]]["p_vals"].push(p["p"]);
      }
      console.log("analyzed:", d);
      var message = this._makeProxyMsg(d);
      var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
      var object : object = message[1];
      var noticeResponse = [stringHTML, object];
      if(noticeResponse == undefined) return
      let msg : string = noticeResponse[0] as string
      let popupContent : object = noticeResponse[1] as object
      if (msg) { this.appendMsg(proxies[0]["cell_id"], proxies[0]["kernel_id"], msg, popupContent); }
    }

  
    private _makeContainer(df_name? : string)  : [HTMLDivElement, HTMLDivElement] {
      /* 
      the template for prompt containers returns top level container and element that 
      the notification should be put into
      */
      let note : HTMLDivElement = document.createElement("div")
      note.append($.parseHTML('<div class="note condensed"><!-- gap --><div class="essential"> <!-- gap --><div class="dropDown"> <!-- gap --><svg class="condensed" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 250 250"> <!-- gap --><path class="cls-4" d="M58.6,226.057L184.69,129,58.6,31.943"/> <!-- gap --></svg> <!-- gap --><svg class="expanded" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 250 250" style="display: none;"> <!-- gap --><path class="cls-4" d="M28.443,62L125.5,187.782,222.557,62"/> <!-- gap --></svg> <!-- gap --></div> <!-- gap --><div class="text"> <!-- gap --><h1>Note Name</h1> <!-- gap --></div> <!-- gap --><div class="close"> <!-- gap --><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500"><path class="prompt-ml-close-svg-path" d="M91.5,93.358L409.461,406.6"/><path class="prompt-ml-close-svg-path" d="M91.5,406.6L409.461,93.358"/></svg></div> <!-- gap --></div> <!-- gap --> <!-- gap --></div> <!-- gap -->')[0])

      let content : HTMLDivElement = document.createElement("div")
      content.classList.add("content")
      $(note).find(".note")[0].append(content)
   
      return [note, content]; 
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
  
      var title = "Variance";
      $(body).find(".essential h1").text(title);

      var payload : object = {
        "title": "Wands Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload);     
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

      var title = "Correlation";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Cups Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload)    
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
  
      var title = "Outliers";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Pentacles Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload)  
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
  
      var title = "Null Entries";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Swords Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload) 
    }
    private _makeResembleMsg(df_name : string, col_name : string) {
  
      let var_line_1 = document.createElement("p");
      let var_line_2 = document.createElement("p");
  
      var_line_1.innerHTML = "The dataframe <b>"+df_name+"</b> contains a column <b>"+col_name+"</b>.";
  
      var_line_2.innerHTML = "Using this column may be discriminatory.";
      
      var [body, area] = this._makeContainer();
      area.appendChild(var_line_1);
      area.appendChild(var_line_2);

      var title = "Protected Column";
      $(body).find(".essential h1").text(title);
  
      var payload : object =  {
        "title": "Resemble Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload)    
    }   
  
    private _makeVarMsg(zip1 : string, zip2 : string, demo : any) {
  
      let var_line_1 = document.createElement("p");
      let var_line_2 = document.createElement("p");
  
      var_line_1.innerHTML = "Zip code <b>"+zip1+"</b> is "+demo[zip1]+"% black";
      var_line_2.innerHTML = "Zip code <b>"+zip2+"</b> is "+demo[zip2]+"% white";
  
      var [body, area] = this._makeContainer();
      area.appendChild(var_line_1);
      area.appendChild(var_line_2);
  
      var title = "Zip Code Demographics";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Var Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload) 
    }
    private _makeOutliersMsg(col_name : string, value : number, std_dev : number, df_name :string) {
  
      let var_line_1 = document.createElement("p");
      let var_line_2 = document.createElement("p");
  
      var_line_1.innerHTML = "The column <b>"+col_name+"</b> in data frame <b>"+df_name+"</b> contains values greater than "+value;
      var_line_2.innerHTML = value + " is "+std_dev.toString().slice(0,5)+" standard deviations above the average for that column";
  
      var [body, area] = this._makeContainer();
      area.appendChild(var_line_1);
      area.appendChild(var_line_2);
  
      var title = "Outliers";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Wands Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload) 
    }
    private _makeEqOddsMsg(notice : any) {
      let msg_l1 = document.createElement("p");
      if (notice["eq"] == "fpr") {
        msg_l1.innerHTML = "Applying a false positive rate equalization to ";
      } else if (notice["eq"] == "fnr") {
        msg_l1.innerHTML = "Applying a false negative rate equalization to ";
      }
  
      msg_l1.innerHTML += notice["model_name"]
      msg_l1.innerHTML += " achieved a training accuracy of "+notice["acc_corr"].toString().slice(0,5);
      msg_l1.innerHTML += " (Original: "+notice["acc_orig"].toString().slice(0,5)+")";
  
      let msg_l2 = document.createElement("p");
      msg_l2.innerHTML = "This correction changed "+notice["num_changed"]+" predictions"; 
  
      let msg_l3 = document.createElement("p"); // more info about correction 
      msg_l3.innerHTML = "This correction was a "
      
      let link = document.createElement("a");
      link.href = "https://aif360.readthedocs.io/en/v0.2.3/modules/postprocessing.html";
      link.innerText = "equalized odds post-processing ";
      
      msg_l3.appendChild(link);
      
      msg_l3.innerHTML += " correction. It used the majority group in "+notice["grp"];
      msg_l3.innerHTML += " as those belonging to the privileged group";
  
      var [body, area] = this._makeContainer(notice["model_name"]);
  
      area.appendChild(msg_l1);
      area.appendChild(msg_l2);
      area.appendChild(msg_l3);

      var title = "Equalized Odds";
      $(body).find(".essential h1").text(title);
  
      var payload : object =  {
        "title": "Equalized Odds Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload) 
    }
    private _makeProxyMsg(d : any) {
      var ul_container = document.createElement("div")
      for (let df_name in d) {
        var label = document.createElement("h3")
        label.innerHTML = `Within ${df_name}`
        ul_container.appendChild(label)
        var df  = d[df_name];
        let ul = document.createElement("ul");
        for(var x = 0; x < df["proxy_col_name"].length; x++) {
          var li = document.createElement("li");
          li.innerHTML = `Column ${df["proxy_col_name"][x]} may be predictive of ${df["sensitive_col_name"][x]}`
          ul.appendChild(li);
         };
         ul_container.appendChild(ul)
      }
  
      var [body, area] = this._makeContainer();
      area.appendChild(ul_container);

      // Expanded view content
      
      var container = $.parseHTML("<div class=\"promptMl proxyColumn\" style=\"padding: 15px; overflow: scroll;\"><h1>Proxy Columns</h1><ul></ul></div>")
      $(container).find("ul").append($.parseHTML(`
      <li>Certain variables in this notebook may encode or have strong correlations with sensitive variables. In some cases, the use of these correlated variables may produce outcomes that are biased. This bias may be undesirable, unethical and in some cases illegal. <a style=\"color: blue; text-decoration; underline\" target=\"_blank\" href=\"PLACEHOLDER\">(Read More)</a></li>
      `))
      $(container).find("ul").append($.parseHTML(`
      <li>This plugin has detected the presence of certain columns in this notebook that may be correlated with sensitive variables. In some instances, this correlation was detected by computing the correlation between the sensitive column and the candidate proxy column. 
        <ul>
          <li>A column may also be correlated with a sensitive variable that is not contained in the data. This plugin also notes when a column may encode data that is known to correlate with a sensitive variable that is not present in the dataset. </li>
        </ul>
      </li>
      `))
      $(container).find("ul").append($.parseHTML(`
      <li>The correlations found or suggested here may or may not be meaningful. There also may be situation-specific correlations that are not detected by this plugin. </li>
      `))
      for (let df_name in d) {
        var label = document.createElement("h3")
        label.innerHTML = `Within <strong>${df_name}</strong>`
        $(container).append(label)
        var df  = d[df_name];
        let ul = document.createElement("ul");
        for(var x = 0; x < df["proxy_col_name"].length; x++) {
          var li = document.createElement("li");
          li.innerHTML = `Column <strong>${df["proxy_col_name"][x]}</strong> ${(df["p_vals"][x] < 0.001) ? "is strongly correlated with" : "may be predictive of"} <strong>${df["sensitive_col_name"][x]}</strong>.` // Rounds to the third decimal place
          ul.appendChild(li);
         };
         $(container).append(ul)
      }
      // Make payload
      var title = "Proxy Column";
      $(body).find(".essential h1").text(title);
      var payload : object =  {
        "title": "Proxy Message",
        "htmlContent": container,
      }

      return new Array(body, payload) 
    }

    private _makePerformanceMsg(notice : any) {
  
      let msg_l1 = document.createElement("p");
      msg_l1.innerHTML = "The model "+notice["model_name"]+" has a training accuracy of "+notice["acc"];
      let msg_l2 = document.createElement("p");
      msg_l2.innerHTML = "The mistakes it makes break down as follows";
  
      let table_elt = document.createElement("table");
      let header = document.createElement("tr");
  
      header.appendChild(document.createElement("th"));
      header.appendChild(document.createElement("th"));
  
      let fpr_header = document.createElement("th");
      let fnr_header = document.createElement("th");
  
      fpr_header.innerHTML = "Pr[Predicted ="+notice["values"]["pos"] +"|Actual="+notice["values"]["neg"]+"]";
      fnr_header.innerHTML = "Pr[Predicted ="+notice["values"]["neg"] +"|Actual="+notice["values"]["pos"]+"]";
  
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
  
      var title = "Performance";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Performance Message",
        "htmlContent": $.parseHTML("<p>Testing...</p>"),
      }

      return new Array(body, payload) 
    }

    private _makeMissingMsg(notice : { [key : string] : { [ key : string ] : any } } ) {
      let msg_l1 = document.createElement("div");
      // msg_l1.innerHTML = "Received: " + JSON.stringify(notice["dfs"]);
      for(var df_name in notice["dfs"]) {
        msg_l1.appendChild($.parseHTML(`<h3>Within ${df_name}</h3>`)[0])
        var df = notice["dfs"][df_name]
        var ul = document.createElement("ul")
        msg_l1.appendChild(ul)
        var cols : { [ key: string ] : number} = df["columns"]
        for(const col_name in cols) {
          var col = cols[col_name]
          if(col == 0) continue
          ul.appendChild($.parseHTML(`<li>Column <strong>${col_name}</strong> is missing <strong>${col}</strong> entries</li>`)[0])
        }
      }
  
      var [body, area] = this._makeContainer();
      area.appendChild(msg_l1);

      // Expanded view content
       var moreInfoContent = $.parseHTML("<div class=\"promptMl missing\" style=\"padding: 15px; overflow: scroll;\"><h1>Missing Data</h1><ul></ul></div>")
      $(moreInfoContent).find("ul").append($.parseHTML(`
        <ul>
          <li>There are a number of reasons why data may be missing. In some instances, 
          it may be due to biased collection practices. It may also be missing due to random 
          error <a href=\"placeholder\"(Read More)</a></li>
          <li>This plugin cannot detect whether the missing data are missing at random or whether 
          they are missing due to observed or unobserved variables.</li>
        </ul>
      `)[0]) // making the static content

      for(var df_name in notice["dfs"]) {
        var df = notice["dfs"][df_name]
        var possible_ul = document.createElement("ul")
        for(const col_name in df["columns"]) {
          var col = cols[col_name]
          if(col == 0) continue
          possible_ul.appendChild($.parseHTML(`<li>Column <strong>${col_name}</strong> is missing <strong>${col}</strong> entries</li>`)[0])
        }
        if($(possible_ul).find("li").length == 0) {
          $(moreInfoContent).append($.parseHTML(`<h3>The data frame ${df_name} is not missing any data`)[0])
        } else {
          $(moreInfoContent).append($.parseHTML(`<h3>The data frame ${df_name} is missing data in ${($(possible_ul).find("li").length > 1) ? "several columns" : "one column"}</h3>`)[0])
          $(moreInfoContent).append(possible_ul)
        }
      } 
      
      // Payload

      var title = "Missing Data Note";
      $(body).find(".essential h1").text(title);
      var payload : object =  {
        "title": title,
        "htmlContent": moreInfoContent,
      }

      return new Array(body, payload) 
    }
  
    // private _getCell(id : string, tracker : INotebookTracker) : Cell {
  
    //   var nb : Notebook = tracker.currentWidget.content;
  
    //   for (let i = 0; i < nb.widgets.length; i++) {
    //     if (nb.widgets[i].model.id == id) {
    //       return nb.widgets[i];
    //     }
    //   }
  
    //   return null;
    // }
  }
  