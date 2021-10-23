// import $ = require('jquery');

export class PopupNotification {

    ////////////////////////////////////////////////////////////
    // Properties
    // Some of these are constants, others record the state of
    // the notification. 
    ////////////////////////////////////////////////////////////
  
    // Given by user
    type: string;
    interactive: boolean;
    title: string;
    // Dynamic
    private _content: HTMLDivElement;
  
    ////////////////////////////////////////////////////////////
    // Helper functions
    // Low-level functions that tend to be repeated often
    ////////////////////////////////////////////////////////////
  
    private _generateBaseElement() : HTMLDivElement {
      var elem = document.createElement("div");
      elem.classList.add("promptMl", "proxyColumn");
      elem.style.cssText = "padding: 15px; overflow: scroll;";
      return elem;
    }
  
    private _generateElement(type : string, content : string) : HTMLElement {
      var elem = document.createElement(type);
      elem.innerHTML = content;
      return elem;
    }
  
    private _stringifyContent(content : any[], top : boolean) : string {
      var returnString = "";
      if(!top)
        returnString += "<ul>"
      for(var i in content) {
        if(typeof content[i] === "string")
          returnString += "<li>" + content[i] + "</li>";
        else
          returnString += this._stringifyContent(content[i], false);
      }
      if(!top)
        returnString += "</ul>"
      return returnString;
    }
  
    ////////////////////////////////////////////////////////////
    // Abstractions
    // Tries to make note generation more intuitive and consistent across
    // different note types and styles.
    ////////////////////////////////////////////////////////////
  
    // Given a string of the header's content, this will automatically add
    // a header to the note at the bottom of the note's content.
    addHeader(content : string) : void  {
      var headerElement = this._generateElement("h2", content);
      this._content.append(headerElement);
    }
  
    // Given a string of the subheader's content, this will automatically add
    // a header to the note at the bottom of the note's content.
    addSubheader(content : string) : void  {
      var headerElement = this._generateElement("h3", content);
      this._content.append(headerElement);
    }
  
    // Given a string of the pargraph's content, this will automatically add
    // a paragraph to the note at the bottom of the note's content.
    addParagraph(content: string) : void {
      var paragraphElement = this._generateElement("p", content);
      this._content.append(paragraphElement);
    }
  
    // Given an array of strings to be included (each index is a bullet point),
    // this adds an unordered list to the bottom of the note's content.
    // Example content could be
    // [
    //    "title",
    //    [
    //      "nested list",
    //      "and then more"
    //    ],
    //    "continued"
    // ]
    // A list of any depth will work as long as the content is composed of strings.
    addList(content: any[]) : void {
      var listElement = this._generateElement("ul", "");
      for(var li in content) {
        if(typeof content[li] === "string")
          listElement.append(this._generateElement("li", content[li]))
        else
          listElement.append(this._generateElement("ul", this._stringifyContent(content[li], true)))
      }
      this._content.append(listElement)
    }
  
    ////////////////////////////////////////////////////////////
    // Functionality
    // Help provide note-level functionality, such as export, wipe, etc.
    ////////////////////////////////////////////////////////////
  
    constructor(type: string, interactive: boolean, title: string) {
      this.type = type;
      this.interactive = interactive;
      this.title = title;
      this._content = this._generateBaseElement();
      this._content.classList.add(type);
    }
  
    // Returns a copy of the note's current state as a node
    // Can easily be inserted into the DOM for program output or
    // for debugging purposes/
    export() : Node {
      return this._content.cloneNode(true);
    }
  
    // Resets the content. Could be helpful for updating contents
    // or user interactions.
    wipe() : void {
      this._content = this._generateBaseElement();
    }
  
    generateCondensed() : HTMLElement {
      return this._generateElement("div", `
        <div class="note condensed">
          <div class="essential">
            <div class="dropDown"><svg xmlns="http://www.w3.org/2000/svg" width="75%" height="75%" viewBox="0 0 500 500">
              <g id="Artboard_1" data-name="Artboard 1">
                <g id="BR">
                  <path id="Perfect_Square" data-name="Perfect Square" class="cls-5" d="M400,485h84V400.114" />
                  <path class="cls-5" d="M472.212,474.212L363.788,365.788" />
                </g>
                <g id="TR">
                  <path id="Perfect_Square-2" data-name="Perfect Square" class="cls-5" d="M479,102.426v-84H394.114" />
                  <path class="cls-5" d="M462.212,32.214L353.788,140.638" />
                </g>
                <g id="TL">
                  <path id="Perfect_Square-3" data-name="Perfect Square" class="cls-5" d="M102.385,19.219h-84v84.886" />
                  <path class="cls-5" d="M33.173,32.007L141.6,140.431" />
                </g>
                <g id="BL">
                  <path id="Perfect_Square-4" data-name="Perfect Square" class="cls-5" d="M18.375,396.99v84h84.886" />
                  <path class="cls-5" d="M29.163,469.2L137.587,360.778" />
                </g>
              </g>
                </svg> </div> 
            <div class="text">
                <h1>${this.title}</h1> 
            </div> 
            <div class="close">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500">
                  <path class="prompt-ml-close-svg-path" d="M91.5,93.358L409.461,406.6" />
                  <path class="prompt-ml-close-svg-path" d="M91.5,406.6L409.461,93.358" />
                </svg>
            </div> 
        </div> 
      </div> `)
    }
  
    generateFormattedOutput(global_notification_count : number, note_count : number) : object[] {
      var payload : object =  {
        "title": this.title,
        "htmlContent": this.export(),
        "typeOfNote": `${this.type}-${global_notification_count}-${note_count}`
      }
      return new Array(this.generateCondensed(), payload) 
    }
  }