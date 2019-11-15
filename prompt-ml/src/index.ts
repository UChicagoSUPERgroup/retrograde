import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';


/**
 * Initialization data for the prompt-ml extension.
 */
const extension: JupyterFrontEndPlugin<void> = {
  id: 'prompt-ml',
  autoStart: true,
  activate: (app: JupyterFrontEnd) => {
    console.log('JupyterLab extension prompt-ml is activated!');
  }
};

export default extension;
