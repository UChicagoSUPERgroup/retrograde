import { 
  Notebook, 
  NotebookActions,
  NotebookPanel
} from "@jupyterlab/notebook";

import {
  ICellModel,
  CodeCell,
  Cell,
} from "@jupyterlab/cells";

import {
  INotebookTracker,
} from "@jupyterlab/notebook";

import {
  ExecutionCount,
} from "@jupyterlab/nbformat";

import { ISignal, Signal } from '@lumino/signaling';
import { IObservableList } from "@jupyterlab/observables";
import { ServerConnection } from "@jupyterlab/services";

import { PromiseDelegate } from "@lumino/coreutils";
import { CodeCellClient } from "./client";

const FIRST_SECTION_NAME = 'intro'

export class Listener {
  /*
   This listens on a notebook and records changes to cells on execution
  */
  private client: CodeCellClient;
  private tracker : INotebookTracker;
  private _infoSignal : Signal<this, any> = new Signal<this, any>(this);
  private notebook : Notebook;

  constructor(client: CodeCellClient, tracker : INotebookTracker) {

    this.tracker = tracker;
    this.client = client;
    this.await();

  }

  get infoSignal(): ISignal<this, string> {
    return this._infoSignal;
  }

  private async await() {
    this.init(this.tracker, this.tracker.currentWidget, this)
    this.tracker.currentChanged.connect((sender, current) => {this.init(sender, current, this)})
  }

  private async init(signalSender : INotebookTracker, currentWidget : NotebookPanel, listener : Listener) {
    if(signalSender.currentWidget != null) {
        await signalSender.currentWidget.revealed;
        listener.notebook = signalSender.currentWidget.content;
        listener.listen();
        listener._ready.resolve(undefined);
    }
  }

  public getNotebook() {
    return this.notebook;
  }

  private listen() {
    var cell: Cell;
    var contents: string;
    var id: string;
    var k_id: string;
    var exec_ct : ExecutionCount;
    //listen to cell change events on notebook model
    this.notebook.model.cells.changed.connect(
      (sender: any, data: IObservableList.IChangedArgs<ICellModel>) => {
        //add section metadata to newly added cells
        if (data.type == 'add') {
          let cell = undefined;
          let current_section = FIRST_SECTION_NAME;
          let iterator = sender.iter();
          //use lumino ArrayIterator API to traverse
          //notebook cells. There is most likely a more natural way
          //to do this, but lumino is poorly documented. Here is the 
          //section of code I am using if you are interested in rewriting this loop
          //https://github.com/jupyterlab/lumino/blob/11ec996c7e7599af38c3b28d546033c578f71e4f/packages/algorithm/src/iter.ts#L387
          while ((cell = iterator.next()) !== undefined) {
            if (cell.metadata.get('section') !== undefined){
                current_section = cell.metadata.get('section');
            }
            else{
              cell.metadata.set('section',current_section);
            };
          };
        };
     });
    //listen for cell execution events
    NotebookActions.executed.connect(
      (signal: any, bunch: object) => {
        cell = (Object(bunch)["cell"] as Cell);
        if (cell instanceof CodeCell) {
          console.log("sent ", cell);
          contents = cell.model.value.text;
	      id = cell.model.id;
          k_id = this.tracker.currentWidget.sessionContext.session.kernel.id;
          exec_ct = (cell as CodeCell).model.executionCount;
          this.client.request(
            "exec", "POST", 
            JSON.stringify({
                "type" : "execute",
                "contents" : contents, 
                "cell_id" : id,
                "kernel" : k_id,
                "exec_ct" : exec_ct,
                "metadata" : JSON.stringify(cell.model.metadata)}),
	        ServerConnection.makeSettings()).
	    then(value => { 
              console.log("received: ",value);
              let obj = JSON.parse(value);
              this._infoSignal.emit(obj); });
        }
      })
  }
  private _ready = new PromiseDelegate<void>();
}
