import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  Cell,
} from "@jupyterlab/cells";
 
import {
  INotebookTracker,
  INotebookModel,
  NotebookPanel,
} from "@jupyterlab/notebook";

import {
  CellListen,
} from "./cell-listener";

import {
    DisposableDelegate, IDisposable,
} from "@phosphor/disposable";

import {
  CommandToolbarButton,
} from "@jupyterlab/apputils";

import {
    DocumentRegistry,
} from "@jupyterlab/docregistry";

const ENABLE_HIST_CMD = "prompt_ml_enable";

class CellPrompter implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel> {

  private app: JupyterFrontEnd;
  /*private tracker: INotebookTracker;*/
 
  constructor(app: JupyterFrontEnd, tracker: INotebookTracker) {
    this.app = app;
    /*this.tracker = tracker;*/
    new CellListen(tracker.currentWidget); 
  }

  public createNew(nb: NotebookPanel, context: DocumentRegistry.IContext<INotebookModel>): IDisposable {
    const btn = new CommandToolbarButton({
      commands: this.app.commands,
      id: ENABLE_HIST_CMD,
    });
    nb.toolbar.insertAfter("cellType", this.app.commands.label(ENABLE_HIST_CMD), btn);
      return new DisposableDelegate(() => {
        btn.dispose();
     });
  }
   
}

/**
 * Initialization data for the prompt-ml extension.
 */
const extension: JupyterFrontEndPlugin<void> = {
  id: 'prompt-ml',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, tracker : INotebookTracker) => {
    console.log("Hello world");
    
    if (tracker.currentWidget) {
      tracker.currentWidget.content.widgets.forEach((cell: Cell) => {
        console.log("cell ", cell.id);
      }); 
    }

    const prompter = new CellPrompter(app, tracker);
    app.docRegistry.addWidgetExtension("Notebook", prompter);
  }

};

export default extension;
