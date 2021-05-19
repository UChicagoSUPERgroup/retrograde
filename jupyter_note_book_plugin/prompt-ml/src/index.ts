import {
  JupyterFrontEnd, JupyterFrontEndPlugin, LabShell
} from '@jupyterlab/application';

import {
  INotebookTracker, NotebookPanel
} from "@jupyterlab/notebook";
import {
  Terminal
} from "@jupyterlab/terminal"
import {
  Widget
} from "@lumino/widgets"

import {
  Listener,
} from "./cell-listener";

import {
  Prompter,
} from "./notifier";

import { CodeCellClient } from "./client";

/**
 * Initialization data for the prompt-ml extension.
 */
const extension: JupyterFrontEndPlugin<void> = {
  id: 'prompt-ml',
  autoStart: true,
  requires: [INotebookTracker, NotebookPanel.IContentFactory],
  activate: (app: JupyterFrontEnd, tracker : INotebookTracker, factory : NotebookPanel.IContentFactory) => {
    const client = new CodeCellClient();
    app.restored.then(() => {
    const listener = new Listener(client, tracker);
    console.log("init listener", listener);
    const prompter = new Prompter(listener, tracker, app, factory);
    console.log("init prompter", prompter);
    console.log("factory", factory);
//    let item : Widget | undefined;
    let widgets = app.shell.widgets("main");
    let widget : Widget | undefined
    console.log("Widgets: ");

    while (true) {
       widget = widgets.next()
       if (! widget) {
          break;
       }
       console.log(widget); 
    }
    app.commands.execute("terminal:create-new").then((terminal : Terminal) => {
      app.shell.add(terminal, "right");
      if (app.shell instanceof LabShell) {
        //(app.shell as LabShell).collapseLeft();
        //(app.shell as LabShell).expandRight();
        app.shell.activateById(terminal.id);
      }
    });
  })
  }
}

export default extension;
