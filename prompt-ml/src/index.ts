import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';
/*
import {
  Cell, CodeCell,
} from "@jupyterlab/cells";
*/ 
import {
  INotebookTracker,
} from "@jupyterlab/notebook";

/**
 * Initialization data for the prompt-ml extension.
 */
const extension: JupyterFrontEndPlugin<void> = {
  id: 'prompt-ml',
  autoStart: true,
  activate: (app: JupyterFrontEnd, tracker : INotebookTracker) => {
    console.log("Hello world");
/**
    const cells: CodeCell[] = [];
    const notebook = tracker.currentWidget.content;
    notebook.widgets.forEach((cell: Cell) => {
      if (cell.model.type == "code") {
        cells.push(cell as CodeCell);
      }
    });
    
    console.log(cells);  
*/
  }
};

export default extension;
