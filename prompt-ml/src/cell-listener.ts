import { 
  NotebookPanel, 
  Notebook, 
} from "@jupyterlab/notebook";

import {
  ICellModel,
} from "@jupyterlab/cells";

import { IObservableList } from "@jupyterlab/observables";

import { PromiseDelegate } from "@phosphor/coreutils";

export class CellListen {
  /*public activeCell: Cell;*/
  /**
  this listens on the notebook for changes, and logs them by cell
  adapted from mkery's Verdant/notebook-listen.ts
  */
  constructor(notebookPanel : NotebookPanel) {
    console.log("init listener");
    this.notebookPanel = notebookPanel;
    console.log("nbpanel = ",notebookPanel);
    this.init();
  }

  private notebook: Notebook;
  private notebookPanel: NotebookPanel;

  private async init() {

    await this.notebookPanel.revealed;
    console.log("notebookpanel revealed");
    this.notebook = this.notebookPanel.content;
    console.log("notebook = ", this.notebook);
    this.listen();
    this._ready.resolve(undefined) /* IDK what this does*/
  }

  private listen() {

    console.log("listening");
    console.log("changed = ",this.notebook.model.cells.changed);

    this.notebook.model.cells.changed.connect(
      (sender: any, data: IObservableList.IChangedArgs<ICellModel>) => {
        console.log("Cell list change type: ", data.type);
        /*TODO: add change type handling*/
      });
  }

  private _ready = new PromiseDelegate<void>();
}
