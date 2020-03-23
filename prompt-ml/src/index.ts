import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  INotebookTracker,
} from "@jupyterlab/notebook";

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
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, tracker : INotebookTracker) => {
    const client = new CodeCellClient();
    const listener = new Listener(client, tracker);
    console.log("init listener", listener);
    const prompter = new Prompter(listener, tracker);
    console.log("init prompter", prompter);
  }
}

export default extension;
