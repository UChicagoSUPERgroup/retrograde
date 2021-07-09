// import {
//   JupyterFrontEnd, JupyterFrontEndPlugin, LabShell
// } from '@jupyterlab/application';

import {
  JupyterFrontEnd, JupyterFrontEndPlugin,
} from '@jupyterlab/application';

import {
  INotebookTracker, NotebookPanel
} from "@jupyterlab/notebook";
// import {
//   Terminal
// } from "@jupyterlab/terminal"

import {
  Widget
} from "@lumino/widgets"

import {
  Listener,
} from "./cell-listener";

import {
  Prompter,
} from "./notifier";

import { MainAreaWidget } from '@jupyterlab/apputils';

import { CodeCellClient } from "./client";
// working jquery import
import $ = require('jquery');

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

    /////////////////////////////////////////////////
    /////////////////////////////////////////////////
    /////////////////////////////////////////////////
    // Preparing side panel
    const content = new Widget();
    const promptWidget = new MainAreaWidget({ content });
    let promptContainer = document.createElement("div");
    promptContainer.setAttribute("style", "height: 100%; width: 100%; margin: 0; padding: 0; background-color: rgba(255,255,255,1);")
    promptContainer.classList.add("prompt-ml-container");
    content.node.appendChild(promptContainer);
    promptWidget.id = "prompt-ml";
    promptWidget.title.label = "PromptML";
    promptWidget.title.closable = true;
    if (!promptWidget.isAttached) {
      // Attach the widget to the main work area if it's not there
      app.shell.add(promptWidget, 'right');
    }
    // Activate the widget
    app.shell.activateById(promptWidget.id);
    /////////////////////////////////////////////////
    /////////////////////////////////////////////////
    /////////////////////////////////////////////////
    // Manage creation of a new panel
    $(".prompt-ml-container").on("prompt-ml:note-added", function(e, passed_args) {
      var payload = passed_args["payload"]
      var popupContent = new Widget();
      var popupWidget = new MainAreaWidget({ "content": popupContent });
      popupWidget.id = "prompt-ml-popup" + (Math.round(Math.random() * 1000));
      var popupContainer = document.createElement("div");
      popupContainer.classList.add("prompt-ml-popup")
      popupContent.node.appendChild(popupContainer);
      popupWidget.title.label = payload["title"];
      popupWidget.title.closable = true;
      app.shell.add(popupWidget, "main");
      $(".prompt-ml-popup").append(payload["htmlContent"]);
    })
    /////////////////////////////////////////////////
    /////////////////////////////////////////////////
    /////////////////////////////////////////////////
    })
  }
}

export default extension;
