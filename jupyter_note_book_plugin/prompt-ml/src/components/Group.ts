import $ = require("jquery");

export class Group {
  ////////////////////////////////////////////////////////////
  // Properties
  // Some of these are constants, others record the state of
  // the notification.
  ////////////////////////////////////////////////////////////

  // Dynamic
  private _content: HTMLDivElement;
  private groupName: string;

  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor(
    groupName: string,
    valueName: string,
    precision: string,
    recall: string,
    f1Score: string,
    fpr: string,
    fnr: string,
    count : string,
    highlights : number[],
    overall : boolean
  ) {
    var name = overall ? "Overall" : groupName + ": " + valueName
    this._content = this._generateBaseElement(
            name,
            precision,
            recall,
            f1Score,
            fpr,
            fnr,
            count,
            highlights,
            overall
    );
    this.groupName = groupName
  }

  ////////////////////////////////////////////////////////////
  // Helper functions
  // Low-level functions that tend to be repeated often
  ////////////////////////////////////////////////////////////

  private _generateBaseElement(
    name: string,
    precision: string,
    recall: string,
    f1Score: string,
    fpr: string,
    fnr: string,
    count : string,
    highlights : number[],
    overall : boolean
  ): HTMLDivElement {
    var elem;
    if (overall) {
      elem = $.parseHTML(`;
      <div class="group" style="background-color:rgba(0, 0, 256, 0.3) ! important;">
        <h4 style="text-align:left">${name}<br/>count=${count}</h4>
      </div>`);
    } else {
      elem = $.parseHTML(`
      <div class="group">
        <h4 style="text-align:left">${name}<br/>count=${count}</h4>
      </div>`);
    }
    var metric_names : string[] = ["Precision", "Recall", "F1 Score", "FPR", "FNR"];
    var metrics : string[] = [precision, recall, f1Score, fpr, fnr];

    var htmlElem = elem[1] as any as HTMLDivElement;
    console.log(metric_names.length);
    console.log(highlights); 
    for (var i = 0; i < metric_names.length; i++) {
      htmlElem.appendChild(this._generateMetric(metric_names[i], metrics[i], highlights[i]))
    }
     
    return htmlElem;
  }

  private _generateMetric(
    metric_name : string,
    metric : string,
    highlight : number   
  ) : HTMLParagraphElement {
    if (highlight == 1) {
      var elem = $.parseHTML(`
        <p style="color:green"><i>${metric_name}: ${metric}</i></p>
      `);
      return elem[1] as any as HTMLParagraphElement;
    } else if (highlight == -1) {
      var elem = $.parseHTML(`
        <p style="color:red"><b>${metric_name}: ${metric}</b></p>
      `);
      return elem[1] as any as HTMLParagraphElement;
    } else {
      var elem = $.parseHTML(`
        <p>${metric_name}: ${metric}</p>
      `);
      return elem[1] as any as HTMLParagraphElement;
    }
  }

  public getGroupName() {
    return this.groupName;
  }

  ////////////////////////////////////////////////////////////
  // Abstractions
  ////////////////////////////////////////////////////////////

  // Given a string of the header's content, this will automatically add
  // a header to the note at the bottom of the note's content.
  export(): HTMLDivElement {
    return this._content;
  }
}
