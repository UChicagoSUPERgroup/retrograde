// import {
//   JupyterFrontEnd, JupyterFrontEndPlugin, LabShell
// } from '@jupyterlab/application';

import {
  JupyterFrontEnd, JupyterFrontEndPlugin, LabShell
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

import {
  BackendRequest
} from './request';

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
  activate: (app: JupyterFrontEnd, tracker : INotebookTracker, factory : NotebookPanel.IContentFactory, shell: LabShell) => {
    // Maintains a list of all open notifications within the environment;
    // Note: these notifications may or may not have been closed
    var openNotes : { [key : string] : any } = [];
    const client = new CodeCellClient();
    app.restored.then(() => {
    const listener = new Listener(client, tracker);
    console.log("init listener", listener);
    // Manage notification updates
    // This function is called by Prompter.appendMsg when a notification
    // had already been generated but more information is sent.
    // Called whenever new information is sent from the backend AND when
    // a note is re-appended to the front window.
    var onUpdate = (payload : { [key : string] : any }, typeOfNote : string) => {
      if(!(typeOfNote in openNotes))
        return
      // find the node of the note being opened
      var node = openNotes[typeOfNote]["widget_content"].node
      var note_container = $(node).find(`.${openNotes[typeOfNote]["elem_id"]}`)
      // remove old children element and append the new, generated version
      note_container.empty().append(payload["htmlContent"])
    };
    const prompter = new Prompter(listener, tracker, app, factory, onUpdate, app.shell as LabShell);
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
    // Temporary user tracking implementation -- should be split into a separate class before final version
    $(document).on("mouseup", function(e) {
      if($(e.target).closest("[prompt-ml-tracking-enabled]").length != 0) {
        var targetElem = $(e.target).closest("[prompt-ml-tracking-enabled]")
        console.log(targetElem)
        BackendRequest.sendTrackPoint("click", `User clicked element with description ${$(targetElem).attr("prompt-ml-tracker-interaction-description")}`)
      }
    });
    (app.shell as LabShell).activeChanged.connect(e => {
      console.log("changed", e)
      if(e.currentWidget.node.classList.contains("prompt-ml-popup")) {
        BackendRequest.sendTrackPoint("widget_changed", `User opened widget with label: ${e.currentWidget.title.label}`)
        console.log("[UserTracking] Sending change request")
      }
    })
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
    $(".prompt-ml-container").on("prompt-ml:note-added", function(e, passed_args) { 
      // This event is fired (originates from notifier.ts) when "expand" is clicked
      // Extract information from the event
      var payload = passed_args["payload"]
      var typeOfNote = payload["typeOfNote"]
      // Refresh openNotes by seeing if an element with that ID exists
      for(var note in openNotes) {
        if($(`#jp-main-dock-panel #${openNotes[note]["id"]}`).length == 0) {
          delete openNotes[note]
        }
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
        // Send the new information to update the note
        // This code is run when the user re-opens a notification
        // on the right side panel but the large window is already open
        onUpdate(payload, typeOfNote)
      } else {
        // Hasn't yet been opened or has since closed; creating the widget
        var popupContent = new Widget();
        var popupWidget = new MainAreaWidget({ "content": popupContent });
        var id = "prompt-ml-popup" + (Math.round(Math.random() * 1000))
        popupWidget.id = id;
        popupWidget.node.classList.add("prompt-ml-popup")
        var popupContainer = document.createElement("div");
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
        $(payload["htmlContent"]).css("padding", "15px")
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
          if(postAdditionChildren.length == 0) {
            console.error("Failed to find new note tab")
            // To do: Add error handling
          } else if(postAdditionChildren.length > 1) {
            console.error("More than one ID identified")
            // To do: Add error handling
          } else {
            // Saving this information for later reference
            openNotes[typeOfNote] = {
              "id": postAdditionChildren[0],
              "elem_id": id,
              "widget": popupWidget,
              "widget_content": popupContent
            }
          }
        }, 150)
      }
      $(".prompt-ml-popup").each(function() {$(this).parent().css("overflow-y", "scroll")}); // override normal jquery styling
    })
    })
  }
}

export default extension;