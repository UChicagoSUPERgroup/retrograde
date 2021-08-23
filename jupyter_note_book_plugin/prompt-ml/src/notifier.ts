
  import {
    JupyterFrontEnd
  } from "@jupyterlab/application"

  import {
    INotebookTracker,
    NotebookPanel,
  } from "@jupyterlab/notebook";
  
  import {
    Listener,
  } from "./cell-listener";

  import $ = require('jquery');

  // Global used to construct unique ID's 
  // This is increased by 1 everytime that a group of notifications
  // Allows us to have a unique ID for every notification so that repeat notes will open the same widget
  var global_notification_count : number = 0 

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
      var newNote = $.parseHTML(msg)

      $(".prompt-ml-container").prepend(newNote) // prepend vs append. prepend makes notes appear at the top, append at the bottom. to discuss during meeting

      $(newNote).click( function() {
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

      // Removing duplicate notes: two options presented -- delete whichever isn't the intended functionality.

      // Option 1: Preventing duplicate notes from re-appearing
                // If someone closes a note or leaves it open, no note will re-appear with the same exact content
                // var divs = $(".prompt-ml-container > div")
                // for(var x = 0; x < divs.length; x++) {
                //     var targetDiv = divs[x]
                //     if($(newNote).is($(targetDiv))) continue
                //     if($(targetDiv).text() == $(newNote).text()) {
                //       // A note with the same text already appears
                //       $(newNote).remove()
                //     }
                // }
      // Option 2: Removing old duplicate notes and re-displaying them
        // If you close a note and this (new) one appears, it will appear as if it jumped to the top and now has not been closed
        var divs = $(".prompt-ml-container > div")
        for(var x = 0; x < divs.length; x++) {
            var targetDiv = divs[x]
            if($(newNote).is($(targetDiv))) continue
            if($(targetDiv).text() == $(newNote).text()) {
            // A note with the same text already appears
            $(targetDiv).remove()
            }
        }
    }

    private _routeNotice(notice : any, note_count : number) {
      if (notice["type"] == "resemble") {
        var message = this._makeResembleMsg(notice["df"], notice["col"], note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "variance") {
        var message = this._makeVarMsg(notice["zip1"], notice["zip2"], notice["demo"], note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "outliers") {
        var message = this._makeOutliersMsg(notice["col_name"], notice["value"], notice["std_dev"], notice["df_name"], note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "model_perf") {
        var message = this._makePerformanceMsg(notice, note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "eq_odds") {
        var message = this._makeEqOddsMsg(notice, note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "proxy") {
        var message = this._makeProxyMsg(notice, note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1];
        return [stringHTML, object];
      } else if (notice["type"] == "missing") {
        var message = this._makeMissingMsg(notice, note_count);
        var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
        var object : object = message[1]
        return [stringHTML, object]
      }else {
        console.log("No notes generated", notice["type"], notice)
      }
    }
  
    private _onInfo(info_object : any) {

      if (info_object["type"] == "multiple") {
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        var notices = info_object["info"][cell_id]
        var note_count : number = 0
        for(const key in notices) {
          var list_of_notes = notices[key]
          if(key == "proxy") {
            this._handleProxies(list_of_notes, note_count)
            note_count += 1
          } else if (key == "error") {
            this._makeErrorMessage(list_of_notes, note_count);
            note_count += 1
          } else {
            for(var x = 0; x < list_of_notes.length; x++) {
              var notice = list_of_notes[x]
              var noticeResponse = this._routeNotice(notice, note_count);
              if(noticeResponse == undefined) return
              let msg : string = noticeResponse[0] as string
              let popupContent : object = noticeResponse[1] as object
              if (msg) { 
                this.appendMsg(cell_id, kernel_id, msg, popupContent);
                note_count += 1
              }
            }
          }

        }
      }
    
      if (info_object["type"] == "resemble") {
        let msg : string = "<div>Column <b>"+info_object["column"]+"</b> resembles "+info_object["category"] +"</div>";
        let payload = {}
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
        note_count += 1
      }
      if (info_object["type"] == "wands") { // categorical variance
        let responseMessage = this._makeWandsMsg(info_object["op"], 
                                              info_object["num_col"],
                                              info_object["var"], 
                                              info_object["cat_col"],
                                              info_object["rank"],
                                              info_object["total"], note_count);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
        note_count += 1
      }
      if (info_object["type"] == "cups") {// correlation
        let responseMessage = this._makeCupsMsg(info_object["col_a"], info_object["col_b"],
                                             info_object["strength"], info_object["rank"], note_count);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
        note_count += 1
      }
      if (info_object["type"] == "pentacles") { // extreme values
        let responseMessage = this._makePentaclesMsg(info_object["col"],
                                                  info_object["strength"],
                                                  info_object["element"],
                                                  info_object["rank"], note_count);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
        note_count += 1
      }
      if (info_object["type"] == "swords") { // undefined
        let responseMessage = this._makeSwordsMsg(info_object["col"], info_object["strength"], info_object["rank"], note_count);
        let msg : string = (responseMessage[0] as HTMLDivElement).outerHTML;
        let payload = responseMessage[1]
        var cell_id = info_object["info"]["cell"]
        var kernel_id = info_object["kernel_id"]
        this.appendMsg(cell_id, kernel_id, msg, payload);
        note_count += 1
      }
      global_notification_count += 1
    } 

    private _handleProxies(proxies : { [ key: string ] : any }[], note_count : number) {
      var d : { [key : string ] : {[key: string] : string[]} } = {};
      for(var x = 0; x < proxies.length; x++) {
        var p : any = proxies[x];
        if(!(p["df"] in d)) d[p["df"]] = {"proxy_col_name": [], "sensitive_col_name": [], "p_vals": []};
        d[p["df"]]["proxy_col_name"].push(p["proxy_col_name"]);
        d[p["df"]]["sensitive_col_name"].push(p["sensitive_col_name"]);
        d[p["df"]]["p_vals"].push(p["p"]);
      }
      var message = this._makeProxyMsg(d, note_count);
      var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
      var object : object = message[1];
      var noticeResponse = [stringHTML, object];
      if(noticeResponse == undefined) return
      let msg : string = noticeResponse[0] as string
      let popupContent : object = noticeResponse[1] as object
      if (msg) { this.appendMsg(proxies[0]["cell_id"], proxies[0]["kernel_id"], msg, popupContent); }
    }

  
    private _makeContainer(df_name? : string)  : HTMLDivElement {
      /* 
      the template for prompt containers returns top level container and element that 
      the notification should be put into
      */
      let note : HTMLDivElement = document.createElement("div")
      note.append($.parseHTML(`<div class="note condensed"><!-- gap --><div class="essential"><!-- gap --><div class="dropDown"><svg xmlns="http://www.w3.org/2000/svg" width="75%" height="75%" viewBox="0 0 500 500"><g id="Artboard_1" data-name="Artboard 1">  <g id="BR"><path id="Perfect_Square" data-name="Perfect Square" class="cls-5" d="M400,485h84V400.114"/><path class="cls-5" d="M472.212,474.212L363.788,365.788"/>  </g>  <g id="TR"><path id="Perfect_Square-2" data-name="Perfect Square" class="cls-5" d="M479,102.426v-84H394.114"/><path class="cls-5" d="M462.212,32.214L353.788,140.638"/>  </g>  <g id="TL"><path id="Perfect_Square-3" data-name="Perfect Square" class="cls-5" d="M102.385,19.219h-84v84.886"/><path class="cls-5" d="M33.173,32.007L141.6,140.431"/>  </g>  <g id="BL"><path id="Perfect_Square-4" data-name="Perfect Square" class="cls-5" d="M18.375,396.99v84h84.886"/><path class="cls-5" d="M29.163,469.2L137.587,360.778"/>  </g></g>  </svg>  </div> <!-- gap --><div class="text"><!-- gap --><h1>Note Name</h1> <!-- gap --></div> <!-- gap --><div class="close"><!-- gap --><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500"><path class="prompt-ml-close-svg-path" d="M91.5,93.358L409.461,406.6" /><path class="prompt-ml-close-svg-path" d="M91.5,406.6L409.461,93.358" /></svg></div> <!-- gap --></div> <!-- gap --><!-- gap --></div> <!-- gap -->`)[0])
   
      return note; 
    }
   
    private _makeWandsMsg(op : string, num_col : string, variance : string, 
                          cat_col : string, rank : number, total : number, note_count : number) {

      var wandsString = `
      <h2>Variance Note</h2>
      <p>The <b>${op}</b> of <b>${num_col}</b> broken down by <b>${cat_col}</b> has variance ${variance.slice(0,5)}</p>
      <p>There are ${ (rank - 1).toString() } combinations of variables with higher variance</p>
      <p><a href="https://en.wikipedia.org/wiki/Variance>What is variance?</a></p>
      `

      
      var body = this._makeContainer();
  
      var title = "Variance";
      $(body).find(".essential h1").text(title);

      var payload : object = {
        "title": "Variance",
        "htmlContent": $.parseHTML(wandsString),
        "typeOfNote": `wands-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload);     
    }
  
    private _makeCupsMsg(col_a : string, col_b : string, strength : string, rank : number, note_count : number) {
  
      var cupsString = `
      <h2>Correlation Note</h2>
      <p><b>${col_a}</b> has a correlation with <b>${col_b}</b> with a strength of ${strength.slice(0, 5)}.</p>
      <p>There are ${(rank - 1).toString()} combinations of variables with higher correlation strength.</p>
      <p><a href="https://en.wikipedia.org/wiki/Pearson_correlation_coefficient">What is correlation?</a></p>
      `
      
      let body = this._makeContainer();

      var title = "Correlation";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Correlation",
        "htmlContent": $.parseHTML(cupsString),
        "typeOfNote": `cups-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload)    
    }
  
    private _makePentaclesMsg(col : string, strength : string, 
                              element : string, rank : number, note_count : number) {
      var pentaclesString = `
      <H2>Outliers Note</h2>
      <p><b>${col}</b> contains the value <b>${element}</b> which is ${strength.slice(0, 5)} standard deviations out from the column mean.</p>
      <p>There are ${(rank - 1).toString()} other variables with more extreme outliers. <a href="https://en.wikipedia.org/wiki/Standard_score">What is an outlier?</a></p>
      `
      
      let body = this._makeContainer();

  
      var title = "Outliers";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Outliers",
        "htmlContent": $.parseHTML(pentaclesString),
        "typeOfNote": `pentacles-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload)  
    }
  
    private _makeSwordsMsg(col : string, strength : string, rank : number, note_count : number) {
  
      let prop : number = parseFloat(strength);
      let pct : number = prop*100;

      var swordsString = `
        <h2>Null Entries Note</h2>
        <p>${pct.toString().slice(0, 5)}% of entries in <b>${col}</b> are null.</p>
        <p>There are ${(rank - 1).toString()} other variables with more null entries.</p>
      `

      let body = this._makeContainer();
      var title = "Null Entries";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Null Entries",
        "htmlContent": $.parseHTML(swordsString),
        "typeOfNote": `swords-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload) 
    }
    private _makeResembleMsg(df_name : string, col_name : string, note_count : number) {
  
      var resembleString = `
        <h2>Protected Column Note</h2>
        <p>The dataframe <b>${df_name}</b> contains a column <b>${col_name}</b>.</p>
        <p>Using this column may be descriminatory.</p>
      `
      
      var body = this._makeContainer();

      var title = "Protected Column";
      $(body).find(".essential h1").text(title);
  
      var payload : object =  {
        "title": "Resemble Message",
        "htmlContent": $.parseHTML(resembleString),
        "typeOfNote": `resemble-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload)    
    }   
  
    private _makeVarMsg(zip1 : string, zip2 : string, demo : any, note_count : number) {
      var varString = `
      <h2>Zip Code Demographics Note</h2>
      <p>Zip code ${zip1} is ${demo[zip1]}% black.</p>
      <p>Zip code ${zip2} is ${demo[zip2]}% white.</p>
      `
  
      var body = this._makeContainer();
  
      var title = "Zip Code Demographics";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Zip Code Demographics",
        "htmlContent": $.parseHTML(varString),
        "typeOfNote": `var-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload) 
    }
    private _makeOutliersMsg(col_name : string, value : number, std_dev : number, df_name : string, note_count : number) {
      var outliersString = `
      <h2>Outliers Note</h2>
      <p>The column <b>${col_name}</b> in data frame <b>${df_name}</b> contains values greater than ${value}.</p>
      <p>${value} is ${std_dev.toString().slice(0, 5)} standard deviations above the average for that column</p>
      `

      var body = this._makeContainer();
  
      var title = "Outliers";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Outliers",
        "htmlContent": $.parseHTML(outliersString),
        "typeOfNote": `outliers-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload) 
    }
    private _makeEqOddsMsg(notice : any, note_count : number) {
      let msg_l1 = document.createElement("p");
      if (notice["eq"] == "fpr") {
        msg_l1.innerHTML = "Applying a false positive rate equalization to ";
      } else if (notice["eq"] == "fnr") {
        msg_l1.innerHTML = "Applying a false negative rate equalization to ";
      }

      var equalizedOddsString = `
        <h2>Equalized Odds Note</h2>
        <p>${notice["model_name"]} acheived a training accuracy of ${notice["acc_corr"].toString().slice(0, 5)} (Original: ${notice["acc_orig"].toString().slice(0, 5)})</p>
        <p>This correction changed ${notice["num_changed"]} predictions.</p>
        <p>This correlation was a <a href="https://aif360.readthedocs.io/en/v0.2.3/modules/postprocessing.html">equalized odds post-processing</a> correction. It used the majority group in ${notice["grp"]} as those beloning to the priviledged group.</p>

      `
      var body = this._makeContainer(notice["model_name"]);


      var title = "Equalized Odds";
      $(body).find(".essential h1").text(title);
  
      var payload : object =  {
        "title": "Equalized Odds",
        "htmlContent": $.parseHTML(equalizedOddsString),
        "typeOfNote": `equalized-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload) 
    }
    private _makeProxyMsg(d : any, note_count : number) {
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
  
      var body = this._makeContainer();

      // Expanded view content
      
      var container = $.parseHTML("<div class=\"promptMl proxyColumn\" style=\"padding: 15px; overflow: scroll;\"><h1>Proxy Columns Note</h1><ul></ul></div>")
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
      var title = "Proxy Columns";
      $(body).find(".essential h1").text(title);
      var payload : object =  {
        "title": "Proxy Columns",
        "htmlContent": container,
        "typeOfNote": `proxy-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload) 
    }

    private _makePerformanceMsg(notice : any, note_count : number) {
  
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
  
      var body = this._makeContainer();
  

      var area = document.createElement("div")
      var noteHeader = document.createElement("h2")
      noteHeader.innerHTML = "Performance Note"
      area.appendChild(noteHeader)
      area.appendChild(msg_l1);
      area.appendChild(msg_l2);
      area.appendChild(table_elt);
  
      var title = "Performance";
      $(body).find(".essential h1").text(title);

      var payload : object =  {
        "title": "Performance",
        "htmlContent": area,
        "typeOfNote": `performance-${global_notification_count}-${note_count}`
      }

      return new Array(body, payload) 
    }

    private _makeMissingMsg(notice : { [key : string] : { [ key : string ] : any } }, note_count : number ) {
      // Create container for the small-view content
      let msg_l1 = document.createElement("div");
      // Create the container for the expanded-view content
      var moreInfoContent = $.parseHTML("<div class=\"promptMl missing\" style=\"padding: 15px; overflow: scroll;\"><h1>Missing Data Note</h1><ul></ul></div>")
      $(moreInfoContent).find("ul").append($.parseHTML(`
        <li>There are a number of reasons why data may be missing. In some instances, 
        it may be due to biased collection practices. It may also be missing due to random 
        error <a href=\"placeholder\"(Read More)</a></li>
        <li>This plugin cannot detect whether the missing data are missing at random or whether 
        they are missing due to observed or unobserved variables.</li>
      `)) // Static content only for now
      // Iterating over every dataframe
      for(var df_name in notice["dfs"]) {
        // Small-view df container
        msg_l1.appendChild($.parseHTML(`<h3>Within ${df_name}</h3>`)[0])
        var df = notice["dfs"][df_name]
        var ul = document.createElement("ul")
        msg_l1.appendChild(ul)
        // Expanded-view df container
        var possible_ul = document.createElement("ul")
        moreInfoContent[0].appendChild($.parseHTML(`<h3>Within ${df_name}</h3>`)[0])
        moreInfoContent[0].appendChild(possible_ul)
        // Iterating over every column
        for(const col_name_index in df["missing_columns"]) {
          // Extract information for the small-view content
          var col_name = df["missing_columns"][col_name_index]
          var col_count = df[col_name]["number_missing"]
          var total_length = df[col_name]["total_length"]
          // Extract the mode (for expanded view)
          var modes = []
          for(const key in df[col_name]) {
            if(key == "total_length" || key == "number_missing") continue
            else modes.push([key, df[col_name][key]["largest_percent"]])
          }
          modes = modes.sort((a : [string, number][][], b : [string, number][][]) => {
              if (a[1] === b[1]) {
                  return 0;
              }
              else {
                  return (a[1] > b[1]) ? -1 : 1;
              }
          })
          // Append the small-view information
          ul.appendChild($.parseHTML(`<li>Column <strong>${col_name}</strong> is missing <strong>${col_count}</strong>/<strong>${total_length}</strong> entries</li>`)[0])
          // Append the expanded-view information
          var cor_col = modes[0][0]
          var percent = df[col_name][cor_col]["largest_percent"]
          var cor_mode = df[col_name][cor_col]["largest_missing_value"]
          possible_ul.appendChild($.parseHTML(`<li>Column <strong>${col_name}</strong> is missing <strong>${col_count}</strong>/<strong>${total_length}</strong> entries</li>`)[0])
          possible_ul.appendChild($.parseHTML(`<ul><li>This occurs most frequently (${percent}%) when ${cor_col} is ${cor_mode}</li></ul>`)[0])
        }
      }
  
      var body = this._makeContainer();

      // Payload

      var title = "Missing Data";
      $(body).find(".essential h1").text(title);
      var payload : object =  {
        "title": title,
        "htmlContent": moreInfoContent,
        "typeOfNote": `missing-${global_notification_count}-${note_count}`
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
  private _makeErrorMessage(notices : { [key : string] : any }[], note_count : number ) {
    // Making expanded view container
    var errorsString = $.parseHTML("<div class='errors'><h2>Errors Note</h2><ul class='model_list'></ul></div>")
    // Adding dynamic content
    var models : { [key : string ] : any }= {}
    for(var x = 0; x < notices.length; x++) {
      var notice = notices[x]
      if(!(notice["model_name"] in models)) models[notice["model_name"]] = []
      models[notice["model_name"]].push({
        "slice": notice["slice"],
        "count": notice["n"],
      })
    }
    for(var model_name in models) {
      var model = models[model_name]
      var slices_string = ""
      for(var x = 0; x < model.length; x++) {
        console.log(model)
        console.log(model[x])
        slices_string += "<li>"
        for(var y = 0; y < model[x]["slice"].length; y++) {
          slices_string += `${model[x]["slice"][y][0]}: ${model[x]["slice"][y][1]}`
          if(y != model[x]["slice"].length - 1) slices_string += ", "
        }
        slices_string += "</li>"
      }
      $(errorsString).find(".model_list").append($.parseHTML(`
        <li><strong>${model_name}</strong> makes mistakes most frequently in:</li>
        <ul>${slices_string}</ul>
      `))
    }
    // Adding static content; creating response object
    var body = this._makeContainer();
    var title = "Errors";
    $(body).find(".essential h1").text(title);
    var payload : object =  {
      "title": "Outliers",
      "htmlContent": errorsString,
      "typeOfNote": `outliers-${global_notification_count}-${note_count}`
    }
    // Handling notification attachment
    var message = new Array(body, payload)
    var stringHTML : string = (message[0] as HTMLDivElement).outerHTML;
    var object : object = message[1];
    var noticeResponse = [stringHTML, object];
    if(noticeResponse == undefined) return
    let msg : string = noticeResponse[0] as string
    let popupContent : object = noticeResponse[1] as object
    if (msg) { this.appendMsg(notices[0]["cell_id"], notices[0]["kernel_id"], msg, popupContent); }
  }
}