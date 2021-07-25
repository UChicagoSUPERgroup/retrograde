// import {
//   JupyterFrontEnd, JupyterFrontEndPlugin, LabShell
// } from '@jupyterlab/application';

import {
  JupyterFrontEnd, JupyterFrontEndPlugin
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
    // Manage opening the expanded view of a widget
    var openNotes : { [key : string] : any } = []
    $(".prompt-ml-container").on("prompt-ml:note-added", function(e, passed_args) { 
      // This event is fired (originates from notifier.ts) when "expand" is clicked
      // Extract information from the event
      var payload = passed_args["payload"]
      var typeOfNote = payload["typeOfNote"]
      console.log(openNotes)
      // Refresh openNotes by seeing if an element with that ID exists
      for(var note in openNotes) {
        if(!($(`#jp-main-dock-panel #${openNotes[note]["id"]}`).length > 0)) delete openNotes[note]
      }
      // Find out if we already have had a note of this type displayed
      if(typeOfNote in openNotes) {
        // Find the index of the tab we've current selected
        var currentIndex = $("#jp-main-dock-panel .lm-TabBar-content.p-TabBar-content").children().index($("#jp-main-dock-panel .lm-TabBar-content.p-TabBar-content .jp-mod-current")[0])
        // Find the index of the tab we want to open 
        var targetIndex = $("#jp-main-dock-panel .lm-TabBar-content.p-TabBar-content").children().index($(`#jp-main-dock-panel .lm-TabBar-content.p-TabBar-content #${openNotes[typeOfNote]["id"]}`)[0])
        // Find the difference and execute next / previous tab that many times
        if(currentIndex > targetIndex) {
          for(var x = 0; x < currentIndex - targetIndex; x++)
            app.commands.execute("application:activate-previous-tab")
        } else {
          for(var x = 0; x < targetIndex - currentIndex; x++)
            app.commands.execute("application:activate-next-tab")
        }
      } else {
        // Hasn't yet been opened or has since closed; creating the widget
        var popupContent = new Widget();
        var popupWidget = new MainAreaWidget({ "content": popupContent });
        var id = "prompt-ml-popup" + (Math.round(Math.random() * 1000))
        popupWidget.id = id;
        var popupContainer = document.createElement("div");
        popupContainer.classList.add("prompt-ml-popup")
        popupContainer.classList.add(id)
        $(popupContainer.parentElement).css("overflow", "scroll")
        popupContent.node.appendChild(popupContainer);
        popupWidget.title.label = payload["title"];
        popupWidget.title.closable = true;
        // Get a list of all the ids before the addition
        var preAdditionChildren : string[] = []
        $("#jp-main-dock-panel .lm-TabBar-content.p-TabBar-content > li.lm-TabBar-tab").each(function() {
          preAdditionChildren.push($(this).attr("id"))
        })
        app.shell.add(popupWidget, "main");
        $(`.${id}`).append(payload["htmlContent"]);
        // Find the id that the tab was given -- see needed fix below
        setTimeout( () => {
          var postAdditionChildren : any[] = []
          // Fix needed -- app.shell.add is async. Therefore, this fires (w/o delay) before the child
          // elements have been updated -- therefore, it can't find the correct id.
          // Current solution is to wait 150ms, but that's an arbitrary number and the implementation should be changed
          $("#jp-main-dock-panel .lm-TabBar-content.p-TabBar-content > li.lm-TabBar-tab").each(function() {
            postAdditionChildren.push($(this).attr("id"))
          }) 
          postAdditionChildren = postAdditionChildren.filter(e => !preAdditionChildren.includes(e))
          console.log("After filter:", postAdditionChildren)
          if(postAdditionChildren.length == 0) {
            console.log("No id found")
            console.log(postAdditionChildren)
            // To do: Add error handling
          } else if(postAdditionChildren.length > 1) {
            console.log("Multiple id's found")
            console.log(postAdditionChildren)
            // To do: Add error handling
          } else {
            console.log(postAdditionChildren[0], " found as the id")
            // Saving this information for later reference
            openNotes[typeOfNote] = {
              "id": postAdditionChildren[0],
              "widget": popupWidget
            }
          }
        }, 150)
      }
    })
    })
  }
}

export default extension;
