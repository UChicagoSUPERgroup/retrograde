import { 
  NotebookPanel, 
  Notebook, 
  NotebookActions,
} from "@jupyterlab/notebook";

import {
  ICellModel,
  CodeCell,
  Cell,
} from "@jupyterlab/cells";

import {
  INotebookTracker,
} from "@jupyterlab/notebook";

import { ISignal, Signal } from '@lumino/signaling';
import { IObservableList } from "@jupyterlab/observables";
import { ServerConnection } from "@jupyterlab/services";

import { PromiseDelegate } from "@phosphor/coreutils";
import { CodeCellClient } from "./client";

export class Listener {
  /*
   This listens on a notebook and records changes to cells on execution
  */
  private client: CodeCellClient;
  private tracker : INotebookTracker;
  private _dataSignal : Signal<this, any> = new Signal<this, any>(this);
  private _modelSignal : Signal<this, any>  = new Signal<this, any>(this);

  constructor(client: CodeCellClient, tracker : INotebookTracker) {

    this.tracker = tracker;
    this.client = client;
    this.init();

  }

  get datasignal(): ISignal<this, string> {
    return this._dataSignal;
  }
  get modelsignal(): ISignal<this, string> {
    return this._modelSignal;
  } 

  private async init() {
    this.listen();
    this._ready.resolve(undefined);
  }

  private listen() {

    var cell: Cell;
    var contents: string;
    var id: string;
    var k_id: string;
//    var notebook: Notebook;
//    var resp: string;

    NotebookActions.executed.connect(
      (signal: any, bunch: object) => {
       
        cell = (Object(bunch)["cell"] as Cell);
//        notebook = (Object(bunch)["notebook"] as Notebook);

        if (cell instanceof CodeCell) {

          console.log("sent ", cell);
          contents = cell.model.value.text;
	  id = cell.model.id;
          k_id = this.tracker.currentWidget.session.kernel.id;
          //todo: should add url/kernel id to differentiate
          this.client.request(
            "exec", "POST", 
            JSON.stringify({
                "contents" : contents, 
                "cell_id" : id, "kernel" : k_id}),
	        ServerConnection.defaultSettings).
	    then(value => { 
              let obj = JSON.parse(value);
              console.log("[prompt-ml] received", obj);
              if ("data" in obj) { this._dataSignal.emit(obj["data"]); };
              if ("model" in obj) { this._modelSignal.emit(obj["model"]); }});
        }
      })
  }

  private _ready = new PromiseDelegate<void>();
}
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
    this.notebook.model.contentChanged.connect(
      (sender: any, data: any) => {
        console.log("notebook changed", data);
    });
  }

  private _ready = new PromiseDelegate<void>();
}
